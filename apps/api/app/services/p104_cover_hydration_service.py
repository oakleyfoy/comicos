"""P104 catalog cover hydration — catalog_cover_assets lifecycle."""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from PIL import Image
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import API_ROOT, get_settings
from app.models import InventoryCopy
from app.models.catalog_cover_assets import (
    CatalogCoverAsset,
    CatalogCoverHydrationRun,
    COVER_ASSET_STATUS_COMPLETE,
    COVER_ASSET_STATUS_DOWNLOADING,
    COVER_ASSET_STATUS_FAILED,
    COVER_ASSET_STATUS_PENDING,
    COVER_ASSET_STATUS_SKIPPED_NO_URL,
    HYDRATION_RUN_STATUS_COMPLETED,
    HYDRATION_RUN_STATUS_FAILED,
    HYDRATION_RUN_STATUS_RUNNING,
)
from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, utc_now
from app.services.catalog_cover_harvest_service import _cover_root, _http_timeout
from app.services.catalog_fingerprint_service import (
    color_histogram_hex,
    fingerprint_image_path,
)
from app.services.cover_images import sha256_raw_bytes
from app.services.p104_hydration_perf import (
    GlobalDownloadRateLimiter,
    HydrateStageTiming,
    P104PerformanceSummary,
)
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label

LOGGER = logging.getLogger(__name__)

TIER_INVENTORY = "inventory"
TIER_UPC = "upc"
TIER_MODERN_MAJOR = "modern_major"
TIER_RECENT = "recent"
TIER_CATALOG = "catalog"

TIER_SCORE = {
    TIER_INVENTORY: 100,
    TIER_UPC: 200,
    TIER_MODERN_MAJOR: 300,
    TIER_RECENT: 400,
    TIER_CATALOG: 500,
}

P104_LOG_DIR = Path("data/p104/runs")
P104_RUN_COUNTER_FLUSH_EVERY = 150
P104_SEQUENTIAL_COMMIT_EVERY = 150
P104_SYNC_ISSUE_FETCH_BATCH = 2500
P104_SYNC_COMMIT_EVERY = 750
P104_SYNC_PROGRESS_EVERY = 1000


@dataclass
class CoverAssetSyncTiming:
    """Wall-clock seconds for sync phase breakdown (queue build only)."""

    inventory_preload: float = 0.0
    upc_preload: float = 0.0
    cover_url_preload: float = 0.0
    asset_preload: float = 0.0
    issue_scan_and_upsert: float = 0.0
    commit: float = 0.0
    total: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "inventory_preload": round(self.inventory_preload, 4),
            "upc_preload": round(self.upc_preload, 4),
            "cover_url_preload": round(self.cover_url_preload, 4),
            "asset_preload": round(self.asset_preload, 4),
            "issue_scan_and_upsert": round(self.issue_scan_and_upsert, 4),
            "commit": round(self.commit, 4),
            "total": round(self.total, 4),
        }

    def bottleneck_label(self) -> str:
        parts = {
            "cover_url_preload": self.cover_url_preload,
            "asset_preload": self.asset_preload,
            "issue_scan_and_upsert": self.issue_scan_and_upsert,
            "commit": self.commit,
            "inventory_preload": self.inventory_preload,
            "upc_preload": self.upc_preload,
        }
        return max(parts, key=parts.get)


@dataclass
class CoverAssetSyncResult:
    """Result of one explicit queue-build pass (sync_limit caps rows touched per pass)."""

    sync_limit: int = 0
    created: int = 0
    updated: int = 0
    skipped_complete: int = 0
    skipped_no_url: int = 0
    skipped_unchanged: int = 0
    catalog_issues_scanned: int = 0
    touched: int = 0
    timing: CoverAssetSyncTiming | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "sync_limit": self.sync_limit,
            "created": self.created,
            "updated": self.updated,
            "skipped_complete": self.skipped_complete,
            "skipped_no_url": self.skipped_no_url,
            "skipped_unchanged": self.skipped_unchanged,
            "catalog_issues_scanned": self.catalog_issues_scanned,
            "touched": self.touched,
        }
        if self.timing is not None:
            payload["timing"] = self.timing.to_dict()
            payload["timing_bottleneck"] = self.timing.bottleneck_label()
        return payload


@dataclass
class P104DryRunReport:
    assets_total: int = 0
    pending: int = 0
    complete: int = 0
    failed: int = 0
    skipped_no_url: int = 0
    downloading: int = 0
    with_resolvable_url: int = 0
    without_url: int = 0
    pilot_limit: int = 0
    sync_limit: int = 0
    pilot_would_process: int = 0
    by_tier: dict[str, int] = field(default_factory=dict)
    sample_issue_ids: list[int] = field(default_factory=list)
    total_catalog_issues: int = 0
    issues_with_asset_row: int = 0
    eligible_with_catalog_image_url: int = 0
    eligible_with_url_not_queued: int = 0
    eligible_without_asset_row: int = 0
    queue_coverage_pct: float = 0.0
    sync: CoverAssetSyncResult = field(default_factory=CoverAssetSyncResult)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assets_total": self.assets_total,
            "pending": self.pending,
            "complete": self.complete,
            "failed": self.failed,
            "skipped_no_url": self.skipped_no_url,
            "downloading": self.downloading,
            "with_resolvable_url": self.with_resolvable_url,
            "without_url": self.without_url,
            "pilot_limit": self.pilot_limit,
            "sync_limit": self.sync_limit,
            "pilot_would_process": self.pilot_would_process,
            "by_tier": dict(self.by_tier),
            "sample_issue_ids": list(self.sample_issue_ids),
            "total_catalog_issues": self.total_catalog_issues,
            "issues_with_asset_row": self.issues_with_asset_row,
            "eligible_with_catalog_image_url": self.eligible_with_catalog_image_url,
            "eligible_with_url_not_queued": self.eligible_with_url_not_queued,
            "eligible_without_asset_row": self.eligible_without_asset_row,
            "queue_coverage_pct": self.queue_coverage_pct,
            "sync": self.sync.to_dict(),
        }


def _derivative_size_map() -> dict[str, int]:
    settings = get_settings()
    out: dict[str, int] = {}
    for part in settings.p104_derivative_sizes.split(","):
        piece = part.strip()
        if not piece or ":" not in piece:
            continue
        name, size = piece.split(":", 1)
        out[name.strip()] = max(32, int(size.strip()))
    defaults = {"thumbnail": 150, "small": 300, "medium": 600, "large": 1200}
    for key, val in defaults.items():
        out.setdefault(key, val)
    return out


def _comicvine_cover_from_external_ids(external_source_ids: dict | None) -> str | None:
    if not external_source_ids:
        return None
    bucket = external_source_ids.get("COMICVINE")
    if not isinstance(bucket, dict):
        return None
    direct = bucket.get("image_url") or bucket.get("cover_image_url") or bucket.get("cover_url")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    for val in bucket.values():
        if isinstance(val, dict):
            url = val.get("image_url") or val.get("cover_image_url") or val.get("cover_url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    return None


def resolve_cover_url_for_issue(
    session: Session,
    issue: CatalogIssue,
    *,
    existing_images: list[CatalogImage] | None = None,
) -> tuple[str | None, str | None]:
    images = existing_images
    if images is None:
        images = list(
            session.exec(
                select(CatalogImage)
                .where(CatalogImage.issue_id == int(issue.id or 0), CatalogImage.image_type == "cover")
                .order_by(CatalogImage.id.asc())
            ).all()
        )
    for image in images:
        url = (image.source_url or "").strip()
        if url:
            source = image.source or "catalog_image"
            return url, source
    cv_url = _comicvine_cover_from_external_ids(issue.external_source_ids)
    if cv_url:
        return cv_url, "COMICVINE_META"
    return None, None


def resolve_cover_url_for_issue_cached(
    issue: CatalogIssue,
    *,
    cover_urls_by_issue: dict[int, tuple[str, str]],
) -> tuple[str | None, str | None]:
    """Resolve cover URL without DB (uses preloaded catalog_image map + issue external ids)."""
    iid = int(issue.id or 0)
    cached = cover_urls_by_issue.get(iid)
    if cached:
        return cached
    cv_url = _comicvine_cover_from_external_ids(issue.external_source_ids)
    if cv_url:
        return cv_url, "COMICVINE_META"
    return None, None


def _preload_cover_urls_by_issue(session: Session) -> dict[int, tuple[str, str]]:
    rows = session.exec(
        select(CatalogImage.issue_id, CatalogImage.source, CatalogImage.source_url)
        .where(CatalogImage.image_type == "cover")
        .where(col(CatalogImage.source_url).is_not(None))
        .where(CatalogImage.source_url != "")
        .order_by(CatalogImage.issue_id.asc(), CatalogImage.id.asc())
    ).all()
    out: dict[int, tuple[str, str]] = {}
    for row in rows:
        issue_id, source, source_url = row if isinstance(row, tuple) else (row.issue_id, row.source, row.source_url)
        if issue_id is None:
            continue
        iid = int(issue_id)
        if iid in out:
            continue
        url = str(source_url or "").strip()
        if not url:
            continue
        out[iid] = (url, str(source or "catalog_image"))
    return out


def _preload_complete_cover_asset_keys(session: Session) -> set[tuple[int, str]]:
    rows = session.exec(
        select(CatalogCoverAsset.catalog_issue_id, CatalogCoverAsset.source_url).where(
            CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE
        )
    ).all()
    out: set[tuple[int, str]] = set()
    for row in rows:
        iid, url = row if isinstance(row, tuple) else (row.catalog_issue_id, row.source_url)
        if iid is None or not url:
            continue
        out.add((int(iid), str(url)))
    return out


def _preload_non_complete_cover_assets(session: Session) -> dict[tuple[int, str], CatalogCoverAsset]:
    rows = session.exec(
        select(CatalogCoverAsset).where(CatalogCoverAsset.status != COVER_ASSET_STATUS_COMPLETE)
    ).all()
    return {(int(a.catalog_issue_id), str(a.source_url)): a for a in rows}


def _print_sync_progress(
    *,
    scanned: int,
    created: int,
    updated: int,
    skipped_complete: int,
    skipped_no_url: int,
    elapsed_s: float,
) -> None:
    ipm = (scanned / elapsed_s) * 60.0 if elapsed_s > 0 else 0.0
    print(
        "P104 sync "
        f"scanned={scanned} "
        f"created={created} "
        f"updated={updated} "
        f"skipped_complete={skipped_complete} "
        f"skipped_no_url={skipped_no_url} "
        f"elapsed={elapsed_s:.1f}s "
        f"issues_per_minute={ipm:.0f}",
        flush=True,
    )


def _issue_year(issue: CatalogIssue) -> int | None:
    if issue.cover_date:
        return int(issue.cover_date.year)
    if issue.release_date:
        return int(issue.release_date.year)
    return None


def _issue_updated_at_utc(issue: CatalogIssue) -> datetime | None:
    if issue.updated_at is None:
        return None
    if issue.updated_at.tzinfo is None:
        return issue.updated_at.replace(tzinfo=timezone.utc)
    return issue.updated_at


def compute_priority_for_issue(
    session: Session,
    issue: CatalogIssue,
    *,
    inventory_ids: set[int],
    upc_ids: set[int],
    publisher_name: str | None,
) -> tuple[int, str]:
    iid = int(issue.id or 0)
    if iid in inventory_ids:
        return TIER_SCORE[TIER_INVENTORY], TIER_INVENTORY
    if iid in upc_ids:
        return TIER_SCORE[TIER_UPC], TIER_UPC
    settings = get_settings()
    year = _issue_year(issue)
    focus = canonical_focus_publisher_label(publisher_name)
    if year is not None and settings.p104_year_from <= year <= settings.p104_year_to and focus is not None:
        return TIER_SCORE[TIER_MODERN_MAJOR], TIER_MODERN_MAJOR
    if _issue_updated_at_utc(issue) and _issue_updated_at_utc(issue) >= datetime.now(timezone.utc) - timedelta(days=30):
        return TIER_SCORE[TIER_RECENT], TIER_RECENT
    return TIER_SCORE[TIER_CATALOG], TIER_CATALOG


def _load_inventory_issue_ids(session: Session) -> set[int]:
    rows = session.exec(
        select(InventoryCopy.catalog_issue_id).where(col(InventoryCopy.catalog_issue_id).is_not(None)).distinct()
    ).all()
    out: set[int] = set()
    for row in rows:
        val = row[0] if isinstance(row, tuple) else row
        if val is not None:
            out.add(int(val))
    return out


def _load_upc_issue_ids(session: Session) -> set[int]:
    rows = session.exec(select(CatalogUpc.issue_id).where(col(CatalogUpc.issue_id).is_not(None)).distinct()).all()
    out: set[int] = set()
    for row in rows:
        val = row[0] if isinstance(row, tuple) else row
        if val is not None:
            out.add(int(val))
    return out


def _asset_dir(session: Session, issue_id: int, asset_id: int) -> Path:
    issue = session.get(CatalogIssue, issue_id)
    series = session.get(CatalogSeries, issue.series_id) if issue else None
    pub_part = str(series.publisher_id if series else "unknown")
    series_part = str(series.id if series else "unknown")
    return _cover_root() / "assets" / pub_part / series_part / str(issue_id) / str(asset_id)


def _resolve_path(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    candidates = [p, Path.cwd() / p, API_ROOT / p]
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def verify_asset_files(asset: CatalogCoverAsset) -> tuple[bool, list[str]]:
    missing: list[str] = []
    checks = {
        "original": asset.original_path,
        "thumbnail": asset.thumbnail_path,
        "small": asset.small_path,
        "medium": asset.medium_path,
        "large": asset.large_path,
    }
    for label, rel in checks.items():
        if not rel:
            missing.append(label)
            continue
        if _resolve_path(rel) is None:
            missing.append(label)
    return len(missing) == 0, missing


def asset_status_counts(session: Session) -> dict[str, int]:
    rows = session.exec(
        select(CatalogCoverAsset.status, func.count())
        .select_from(CatalogCoverAsset)
        .group_by(CatalogCoverAsset.status)
    ).all()
    out: dict[str, int] = {}
    for status, count in rows:
        out[str(status)] = int(count if not isinstance(count, tuple) else count[0])
    return out


def _count_catalog_issues(session: Session) -> int:
    val = session.exec(select(func.count()).select_from(CatalogIssue)).one()
    return int(val[0] if isinstance(val, tuple) else val)


def _count_issues_with_asset_row(session: Session) -> int:
    row = session.exec(select(func.count(func.distinct(CatalogCoverAsset.catalog_issue_id)))).one()
    return int(row[0] if isinstance(row, tuple) else row)


def _count_issues_with_catalog_image_url(session: Session) -> int:
    row = session.exec(
        select(func.count(func.distinct(CatalogImage.issue_id)))
        .select_from(CatalogImage)
        .where(CatalogImage.image_type == "cover")
        .where(col(CatalogImage.source_url).is_not(None))
        .where(CatalogImage.source_url != "")
    ).one()
    return int(row[0] if isinstance(row, tuple) else row)


def _issues_with_complete_asset_ids(session: Session) -> set[int]:
    rows = session.exec(
        select(CatalogCoverAsset.catalog_issue_id)
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE)
        .distinct()
    ).all()
    out: set[int] = set()
    for row in rows:
        val = row[0] if isinstance(row, tuple) else row
        if val is not None:
            out.add(int(val))
    return out


def survey_catalog_cover_queue(session: Session) -> dict[str, Any]:
    """Read-only queue/eligibility snapshot (no sync)."""
    total_issues = _count_catalog_issues(session)
    issues_with_asset = _count_issues_with_asset_row(session)
    with_image_url = _count_issues_with_catalog_image_url(session)
    complete_ids = _issues_with_complete_asset_ids(session)
    eligible_without_asset = max(0, with_image_url - len(complete_ids))
    # Issues that have a catalog_image URL but no asset row yet
    queued_issue_ids = {
        int(r[0] if isinstance(r, tuple) else r)
        for r in session.exec(select(CatalogCoverAsset.catalog_issue_id).distinct()).all()
        if r is not None
    }
    image_url_issue_ids = {
        int(r[0] if isinstance(r, tuple) else r)
        for r in session.exec(
            select(CatalogImage.issue_id)
            .where(CatalogImage.image_type == "cover")
            .where(col(CatalogImage.source_url).is_not(None))
            .where(CatalogImage.source_url != "")
            .distinct()
        ).all()
        if r is not None
    }
    url_not_queued = len(image_url_issue_ids - queued_issue_ids)
    counts = asset_status_counts(session)
    asset_total = sum(counts.values())
    coverage = round(100.0 * issues_with_asset / total_issues, 2) if total_issues else 0.0
    return {
        "total_catalog_issues": total_issues,
        "asset_rows": asset_total,
        "issues_with_asset_row": issues_with_asset,
        "eligible_with_catalog_image_url": with_image_url,
        "eligible_without_asset_row": eligible_without_asset,
        "eligible_with_url_not_queued": url_not_queued,
        "queue_coverage_pct": coverage,
        "asset_status": counts,
    }


def sync_cover_assets_batch(session: Session, *, sync_limit: int) -> CoverAssetSyncResult:
    """
    Explicit queue-build: scan catalog_issue in id order and upsert asset rows.

    Stops after ``sync_limit`` rows are created or updated (non-complete assets only).
    Completed assets are never modified. Issues without a resolvable URL are skipped
    and do not count toward sync_limit.
    """
    wall = time.perf_counter()
    timing = CoverAssetSyncTiming()
    result = CoverAssetSyncResult(sync_limit=int(sync_limit), timing=timing)
    if sync_limit <= 0:
        timing.total = time.perf_counter() - wall
        return result

    t0 = time.perf_counter()
    inventory_ids = _load_inventory_issue_ids(session)
    timing.inventory_preload = time.perf_counter() - t0

    t0 = time.perf_counter()
    upc_ids = _load_upc_issue_ids(session)
    timing.upc_preload = time.perf_counter() - t0

    t0 = time.perf_counter()
    cover_urls_by_issue = _preload_cover_urls_by_issue(session)
    timing.cover_url_preload = time.perf_counter() - t0

    t0 = time.perf_counter()
    complete_keys = _preload_complete_cover_asset_keys(session)
    assets_by_issue_url = _preload_non_complete_cover_assets(session)
    timing.asset_preload = time.perf_counter() - t0

    scan_start = time.perf_counter()
    pending_commit = 0
    last_id = 0

    while result.touched < sync_limit:
        batch = list(
            session.exec(
                select(CatalogIssue, CatalogPublisher.name)
                .join(CatalogPublisher, CatalogIssue.publisher_id == CatalogPublisher.id, isouter=True)
                .where(col(CatalogIssue.id) > last_id)
                .order_by(col(CatalogIssue.id).asc())
                .limit(P104_SYNC_ISSUE_FETCH_BATCH)
            ).all()
        )
        if not batch:
            break

        for issue, pub_name in batch:
            iid = int(issue.id or 0)
            last_id = iid
            result.catalog_issues_scanned += 1

            url, source = resolve_cover_url_for_issue_cached(
                issue, cover_urls_by_issue=cover_urls_by_issue
            )
            existing = assets_by_issue_url.get((iid, url)) if url else None
            if not url:
                result.skipped_no_url += 1
            elif (iid, url) in complete_keys:
                result.skipped_complete += 1
            else:
                score, tier = compute_priority_for_issue(
                    session, issue, inventory_ids=inventory_ids, upc_ids=upc_ids, publisher_name=pub_name
                )
                if (
                    existing is not None
                    and existing.priority_score == score
                    and existing.priority_tier == tier
                    and (source or existing.source) == existing.source
                ):
                    result.skipped_unchanged += 1
                else:
                    now = utc_now()
                    if existing is None:
                        asset = CatalogCoverAsset(
                            catalog_issue_id=iid,
                            source=source or "UNKNOWN",
                            source_url=url,
                            status=COVER_ASSET_STATUS_PENDING,
                            priority_score=score,
                            priority_tier=tier,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(asset)
                        assets_by_issue_url[(iid, url)] = asset
                        result.created += 1
                    else:
                        existing.priority_score = score
                        existing.priority_tier = tier
                        existing.source = source or existing.source
                        existing.updated_at = now
                        session.add(existing)
                        result.updated += 1

                    result.touched += 1
                    pending_commit += 1

                    if pending_commit >= P104_SYNC_COMMIT_EVERY:
                        t_commit = time.perf_counter()
                        session.commit()
                        timing.commit += time.perf_counter() - t_commit
                        pending_commit = 0

                    if result.touched >= sync_limit:
                        if result.catalog_issues_scanned % P104_SYNC_PROGRESS_EVERY == 0:
                            _print_sync_progress(
                                scanned=result.catalog_issues_scanned,
                                created=result.created,
                                updated=result.updated,
                                skipped_complete=result.skipped_complete,
                                skipped_no_url=result.skipped_no_url,
                                elapsed_s=time.perf_counter() - wall,
                            )
                        break

            if result.catalog_issues_scanned % P104_SYNC_PROGRESS_EVERY == 0:
                _print_sync_progress(
                    scanned=result.catalog_issues_scanned,
                    created=result.created,
                    updated=result.updated,
                    skipped_complete=result.skipped_complete,
                    skipped_no_url=result.skipped_no_url,
                    elapsed_s=time.perf_counter() - wall,
                )

        if result.touched >= sync_limit:
            break

    timing.issue_scan_and_upsert = time.perf_counter() - scan_start
    if pending_commit > 0:
        t_commit = time.perf_counter()
        session.commit()
        timing.commit += time.perf_counter() - t_commit
    else:
        session.flush()

    timing.total = time.perf_counter() - wall
    LOGGER.info(
        "P104 sync complete limit=%s scanned=%s touched=%s timing=%s bottleneck=%s",
        sync_limit,
        result.catalog_issues_scanned,
        result.touched,
        timing.to_dict(),
        timing.bottleneck_label(),
    )
    _print_sync_progress(
        scanned=result.catalog_issues_scanned,
        created=result.created,
        updated=result.updated,
        skipped_complete=result.skipped_complete,
        skipped_no_url=result.skipped_no_url,
        elapsed_s=timing.total,
    )
    return result


def _retry_ready(asset: CatalogCoverAsset) -> bool:
    if asset.status == COVER_ASSET_STATUS_PENDING:
        return True
    if asset.status != COVER_ASSET_STATUS_FAILED:
        return False
    if asset.next_retry_at is None:
        return True
    return asset.next_retry_at <= datetime.now(timezone.utc)


def _mark_failed(session: Session, asset: CatalogCoverAsset, error: str) -> None:
    settings = get_settings()
    asset.download_attempts += 1
    asset.last_error = error[:2000]
    asset.status = COVER_ASSET_STATUS_FAILED
    if asset.download_attempts >= settings.p104_max_retries:
        asset.next_retry_at = None
    else:
        backoff = settings.p104_retry_backoff_base_seconds * math.pow(2, asset.download_attempts - 1)
        asset.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
    asset.updated_at = utc_now()
    session.add(asset)


def _sleep_for_rate_limit(last_at: float | None) -> float:
    settings = get_settings()
    per_min = max(1.0, float(settings.p104_downloads_per_minute))
    min_interval = 60.0 / per_min
    now = time.perf_counter()
    if last_at is not None and now - last_at < min_interval:
        time.sleep(min_interval - (now - last_at))
        now = time.perf_counter()
    return now


def _download_bytes(url: str) -> tuple[bytes, str | None]:
    settings = get_settings()
    headers = {"User-Agent": settings.catalog_import_user_agent}
    response = httpx.get(
        url,
        timeout=_http_timeout(30.0),
        follow_redirects=True,
        headers=headers,
    )
    response.raise_for_status()
    body = response.content
    if not body:
        raise RuntimeError("empty response body")
    return body, response.headers.get("content-type")


def _write_derivatives(
    session: Session,
    asset: CatalogCoverAsset,
    original: Path,
    timing: HydrateStageTiming | None = None,
) -> Path:
    asset_id = int(asset.id or 0)
    issue_id = int(asset.catalog_issue_id)
    base_dir = _asset_dir(session, issue_id, asset_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    sizes = _derivative_size_map()
    with Image.open(original) as img:
        rgb = img.convert("RGB")
        orig_w, orig_h = rgb.size
        original_dest = base_dir / "original.bin"
        t_orig = time.perf_counter()
        if original != original_dest:
            original_dest.write_bytes(original.read_bytes())
        asset.original_path = str(original_dest)
        asset.width = orig_w
        asset.height = orig_h
        asset.file_size = original_dest.stat().st_size
        if timing is not None:
            timing.original_file_write += time.perf_counter() - t_orig

        t_sha = time.perf_counter()
        asset.original_sha256 = sha256_raw_bytes(original_dest.read_bytes())
        if timing is not None:
            timing.sha256 += time.perf_counter() - t_sha

        mapping = {
            "thumbnail": "thumbnail_path",
            "small": "small_path",
            "medium": "medium_path",
            "large": "large_path",
        }
        medium_path: Path | None = None
        t_der = time.perf_counter()
        for size_name, attr in mapping.items():
            max_side = sizes.get(size_name, 300)
            copy = rgb.copy()
            copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out = base_dir / f"{size_name}.jpg"
            copy.save(out, format="JPEG", quality=85, optimize=True)
            setattr(asset, attr, str(out))
            if size_name == "medium":
                medium_path = out
        if timing is not None:
            timing.derivative_resize_write += time.perf_counter() - t_der
        if medium_path is None:
            medium_path = base_dir / "medium.jpg"
    return medium_path


def _apply_hashes_from_medium(
    asset: CatalogCoverAsset,
    medium_path: Path,
    timing: HydrateStageTiming | None = None,
) -> None:
    t_hash = time.perf_counter()
    phash, dhash, ahash = fingerprint_image_path(medium_path)
    if timing is not None:
        timing.phash_ahash_dhash += time.perf_counter() - t_hash

    t_color = time.perf_counter()
    colorhash = color_histogram_hex(medium_path)
    if timing is not None:
        timing.color_histogram += time.perf_counter() - t_color

    with Image.open(medium_path) as img:
        width, height = img.size
    file_size = medium_path.stat().st_size
    asset.perceptual_hash = str(phash)
    asset.average_hash = str(ahash)
    asset.difference_hash = str(dhash)
    asset.color_histogram = str(colorhash)
    asset.width = int(width)
    asset.height = int(height)
    asset.file_size = int(file_size)


def _resolve_asset_url(session: Session, asset: CatalogCoverAsset, timing: HydrateStageTiming | None) -> str:
    t0 = time.perf_counter()
    url = (asset.source_url or "").strip()
    if not url:
        issue = session.get(CatalogIssue, int(asset.catalog_issue_id))
        if issue is not None:
            resolved_url, source = resolve_cover_url_for_issue(session, issue)
            if resolved_url:
                url = resolved_url.strip()
                asset.source_url = url
                if source:
                    asset.source = source
    if timing is not None:
        timing.url_resolve += time.perf_counter() - t0
    return url


def hydrate_cover_asset(
    session: Session,
    asset: CatalogCoverAsset,
    *,
    dry_run: bool = False,
    reprocess: bool = False,
    rate_limiter: GlobalDownloadRateLimiter | None = None,
    staging_path: Path | None = None,
    timing: HydrateStageTiming | None = None,
    hydration_run_id: int | None = None,
) -> str:
    if asset.status == COVER_ASSET_STATUS_COMPLETE and asset.verified_at is not None and not reprocess:
        return COVER_ASSET_STATUS_COMPLETE

    t_asset = time.perf_counter()
    stage = timing if timing is not None else HydrateStageTiming()

    url = _resolve_asset_url(session, asset, stage)
    if not url:
        asset.status = COVER_ASSET_STATUS_SKIPPED_NO_URL
        asset.last_error = "no source_url"
        asset.updated_at = utc_now()
        session.add(asset)
        if timing is not None:
            timing.total = time.perf_counter() - t_asset
        return COVER_ASSET_STATUS_SKIPPED_NO_URL

    if dry_run:
        return COVER_ASSET_STATUS_PENDING

    asset.status = COVER_ASSET_STATUS_DOWNLOADING
    asset.updated_at = utc_now()
    session.add(asset)
    session.flush()

    asset_id = int(asset.id or 0)
    issue_id = int(asset.catalog_issue_id)
    base_dir = _asset_dir(session, issue_id, asset_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    staging = staging_path if staging_path is not None else base_dir / "download.bin"

    try:
        if staging_path is None:
            if rate_limiter is not None:
                rate_limiter.wait()
            t_dl = time.perf_counter()
            body, _ = _download_bytes(url)
            stage.download += time.perf_counter() - t_dl
            t_st = time.perf_counter()
            staging.write_bytes(body)
            stage.staging_write += time.perf_counter() - t_st

        medium_path = _write_derivatives(session, asset, staging, stage)
        _apply_hashes_from_medium(asset, medium_path, stage)
        ok, missing = verify_asset_files(asset)
        if not ok:
            raise RuntimeError(f"missing files after write: {missing}")
        now = utc_now()
        asset.status = COVER_ASSET_STATUS_COMPLETE
        asset.downloaded_at = now
        asset.verified_at = now
        asset.last_error = None
        asset.updated_at = now
        if hydration_run_id is not None:
            asset.last_hydration_run_id = int(hydration_run_id)
        t_db = time.perf_counter()
        session.add(asset)
        session.flush()
        stage.db_update_commit += time.perf_counter() - t_db
        if timing is not None:
            timing.total = time.perf_counter() - t_asset
        return COVER_ASSET_STATUS_COMPLETE
    except Exception as exc:
        _mark_failed(session, asset, str(exc))
        if timing is not None:
            timing.total = time.perf_counter() - t_asset
        return COVER_ASSET_STATUS_FAILED


@dataclass
class _StagingDownloadResult:
    asset_id: int
    staging_path: Path | None = None
    error: str | None = None
    skip_processing: bool = False
    timing: HydrateStageTiming = field(default_factory=HydrateStageTiming)


def _download_asset_to_staging(
    engine: Any,
    asset_id: int,
    staging_path: Path,
    rate_limiter: GlobalDownloadRateLimiter,
    *,
    reprocess: bool,
) -> _StagingDownloadResult:
    timing = HydrateStageTiming()
    with Session(engine, expire_on_commit=False) as session:
        asset = session.get(CatalogCoverAsset, asset_id)
        if asset is None:
            return _StagingDownloadResult(asset_id, error="missing asset", timing=timing)
        if asset.status == COVER_ASSET_STATUS_COMPLETE and asset.verified_at is not None and not reprocess:
            return _StagingDownloadResult(asset_id, skip_processing=True, timing=timing)
        url = _resolve_asset_url(session, asset, timing)
        session.add(asset)
        session.commit()
        if not url:
            return _StagingDownloadResult(asset_id, error="no source_url", timing=timing)

    rate_limiter.wait()
    try:
        t_dl = time.perf_counter()
        body, _ = _download_bytes(url)
        timing.download = time.perf_counter() - t_dl
        t_st = time.perf_counter()
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path.write_bytes(body)
        timing.staging_write = time.perf_counter() - t_st
        return _StagingDownloadResult(asset_id, staging_path=staging_path, timing=timing)
    except Exception as exc:
        return _StagingDownloadResult(asset_id, error=str(exc), timing=timing)


def _reload_hydration_run(session: Session, run_id: int) -> CatalogCoverHydrationRun:
    session.expire_all()
    run = session.get(CatalogCoverHydrationRun, run_id)
    if run is None:
        raise RuntimeError(f"hydration run {run_id} missing")
    session.refresh(run)
    return run


class _RunCounterAccumulator:
    """Batch run counter DB updates (concurrent hydration)."""

    def __init__(self, engine: Any, run_id: int, *, flush_every: int = P104_RUN_COUNTER_FLUSH_EVERY) -> None:
        self._engine = engine
        self._run_id = run_id
        self._flush_every = max(1, flush_every)
        self._lock = threading.Lock()
        self._pending_completed = 0
        self._pending_downloaded = 0
        self._pending_failed = 0
        self._pending_skipped = 0
        self._since_flush = 0

    def record(self, outcome: str) -> None:
        with self._lock:
            if outcome == COVER_ASSET_STATUS_COMPLETE:
                self._pending_completed += 1
                self._pending_downloaded += 1
            elif outcome == COVER_ASSET_STATUS_SKIPPED_NO_URL:
                self._pending_skipped += 1
            elif outcome == COVER_ASSET_STATUS_FAILED:
                self._pending_failed += 1
            else:
                return
            self._since_flush += 1
            if self._since_flush >= self._flush_every:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if (
            self._pending_completed == 0
            and self._pending_downloaded == 0
            and self._pending_failed == 0
            and self._pending_skipped == 0
        ):
            return
        with Session(self._engine, expire_on_commit=False) as session:
            run = session.get(CatalogCoverHydrationRun, self._run_id)
            if run is None:
                return
            run.completed += self._pending_completed
            run.downloaded += self._pending_downloaded
            run.failed += self._pending_failed
            run.skipped_no_url += self._pending_skipped
            session.add(run)
            session.commit()
        self._pending_completed = 0
        self._pending_downloaded = 0
        self._pending_failed = 0
        self._pending_skipped = 0
        self._since_flush = 0


def _process_staged_asset(
    engine: Any,
    run_id: int,
    download: _StagingDownloadResult,
    *,
    reprocess: bool,
    perf: P104PerformanceSummary,
    counter_acc: _RunCounterAccumulator,
) -> tuple[int, str, CatalogCoverAsset | None]:
    timing = download.timing
    t_asset = time.perf_counter()
    outcome = COVER_ASSET_STATUS_FAILED
    asset_ref: CatalogCoverAsset | None = None

    with Session(engine, expire_on_commit=False) as session:
        asset = session.get(CatalogCoverAsset, download.asset_id)
        if asset is None:
            perf.add(timing)
            counter_acc.record(COVER_ASSET_STATUS_FAILED)
            return download.asset_id, COVER_ASSET_STATUS_FAILED, None
        asset_ref = asset

        if download.skip_processing:
            outcome = COVER_ASSET_STATUS_COMPLETE
        elif download.error == "no source_url":
            asset.status = COVER_ASSET_STATUS_SKIPPED_NO_URL
            asset.last_error = "no source_url"
            asset.updated_at = utc_now()
            session.add(asset)
            t_db = time.perf_counter()
            session.commit()
            timing.db_update_commit += time.perf_counter() - t_db
            outcome = COVER_ASSET_STATUS_SKIPPED_NO_URL
        elif download.error:
            _mark_failed(session, asset, download.error)
            t_db = time.perf_counter()
            session.commit()
            timing.db_update_commit += time.perf_counter() - t_db
            outcome = COVER_ASSET_STATUS_FAILED
        elif download.staging_path is None:
            _mark_failed(session, asset, download.error or "download failed")
            t_db = time.perf_counter()
            session.commit()
            timing.db_update_commit += time.perf_counter() - t_db
            outcome = COVER_ASSET_STATUS_FAILED
        else:
            outcome = hydrate_cover_asset(
                session,
                asset,
                reprocess=reprocess,
                staging_path=download.staging_path,
                timing=timing,
                hydration_run_id=run_id,
            )
            t_db = time.perf_counter()
            session.commit()
            timing.db_update_commit += time.perf_counter() - t_db

        timing.total = time.perf_counter() - t_asset
        perf.add(timing)

    if not download.skip_processing:
        counter_acc.record(outcome)
    return download.asset_id, outcome, asset_ref


def _run_p104_hydration_concurrent(
    engine: Any,
    run: CatalogCoverHydrationRun,
    work: list[CatalogCoverAsset],
    *,
    download_workers: int,
    process_workers: int,
    downloads_per_minute: float,
    reprocess: bool,
    perf: P104PerformanceSummary,
    on_asset_processed: Callable[[int, CatalogCoverAsset, CatalogCoverHydrationRun, str], None] | None,
) -> _RunCounterAccumulator:
    run_id = int(run.id or 0)
    staging_root = P104_LOG_DIR / f"staging_run_{run_id}"
    staging_root.mkdir(parents=True, exist_ok=True)
    rate_limiter = GlobalDownloadRateLimiter(downloads_per_minute)
    counter_acc = _RunCounterAccumulator(engine, run_id)
    processed_lock = threading.Lock()
    processed_index = 0

    def _notify(asset_id: int, outcome: str, asset_hint: CatalogCoverAsset | None) -> None:
        nonlocal processed_index
        if on_asset_processed is None:
            return
        with processed_lock:
            processed_index += 1
            index = processed_index
        with Session(engine, expire_on_commit=False) as session:
            run_row = _reload_hydration_run(session, run_id)
            asset_row = session.get(CatalogCoverAsset, asset_id) or asset_hint
            if asset_row is not None:
                on_asset_processed(index, asset_row, run_row, outcome)

    with ThreadPoolExecutor(max_workers=max(1, download_workers)) as download_pool:
        download_futures = {
            download_pool.submit(
                _download_asset_to_staging,
                engine,
                int(asset.id or 0),
                staging_root / f"{int(asset.id or 0)}.bin",
                rate_limiter,
                reprocess=reprocess,
            ): int(asset.id or 0)
            for asset in work
        }
        with ThreadPoolExecutor(max_workers=max(1, process_workers)) as process_pool:
            process_futures = []
            for dl_future in as_completed(download_futures):
                dl_result = dl_future.result()
                process_futures.append(
                    process_pool.submit(
                        _process_staged_asset,
                        engine,
                        run_id,
                        dl_result,
                        reprocess=reprocess,
                        perf=perf,
                        counter_acc=counter_acc,
                    )
                )
            for proc_future in as_completed(process_futures):
                asset_id, outcome, asset_hint = proc_future.result()
                _notify(asset_id, outcome, asset_hint)

    counter_acc.flush()
    return counter_acc


def _hydration_progress_summary(
    run: CatalogCoverHydrationRun,
    *,
    elapsed_seconds: float,
    download_workers: int,
    process_workers: int,
    downloads_per_minute: float,
) -> dict[str, Any]:
    completed = int(run.completed)
    covers_per_minute = (completed / elapsed_seconds) * 60.0 if elapsed_seconds > 0 else 0.0
    return {
        "run_id": int(run.id or 0),
        "queued": int(run.queued),
        "completed": completed,
        "failed": int(run.failed),
        "skipped_no_url": int(run.skipped_no_url),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "covers_per_minute": round(covers_per_minute, 2),
        "download_workers": download_workers,
        "process_workers": process_workers,
        "downloads_per_minute": downloads_per_minute,
    }


def _start_run(session: Session, *, mode: str, limit: int) -> CatalogCoverHydrationRun:
    run = CatalogCoverHydrationRun(
        mode=mode,
        limit=limit,
        status=HYDRATION_RUN_STATUS_RUNNING,
        requested=limit,
        started_at=utc_now(),
    )
    session.add(run)
    session.flush()
    return run


def _finish_run(session: Session, run_id: int, *, log_payload: dict) -> CatalogCoverHydrationRun:
    P104_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = P104_LOG_DIR / f"run_{run_id}.json"
    log_path.write_text(json.dumps(log_payload, indent=2, default=str), encoding="utf-8")
    run = _reload_hydration_run(session, run_id)
    run.log_path = str(log_path)
    run.finished_at = utc_now()
    run.status = HYDRATION_RUN_STATUS_COMPLETED
    session.add(run)
    return run


def run_p104_dry_run(
    session: Session,
    *,
    pilot_limit: int = 100,
    sync_limit: int = 0,
) -> P104DryRunReport:
    survey = survey_catalog_cover_queue(session)
    sync_result = sync_cover_assets_batch(session, sync_limit=sync_limit)
    counts = asset_status_counts(session)
    report = P104DryRunReport(
        assets_total=sum(counts.values()),
        pending=int(counts.get(COVER_ASSET_STATUS_PENDING, 0)),
        complete=int(counts.get(COVER_ASSET_STATUS_COMPLETE, 0)),
        failed=int(counts.get(COVER_ASSET_STATUS_FAILED, 0)),
        skipped_no_url=int(counts.get(COVER_ASSET_STATUS_SKIPPED_NO_URL, 0)),
        downloading=int(counts.get(COVER_ASSET_STATUS_DOWNLOADING, 0)),
        pilot_limit=pilot_limit,
        sync_limit=sync_limit,
        total_catalog_issues=int(survey["total_catalog_issues"]),
        issues_with_asset_row=int(survey["issues_with_asset_row"]),
        eligible_with_catalog_image_url=int(survey["eligible_with_catalog_image_url"]),
        eligible_with_url_not_queued=int(survey["eligible_with_url_not_queued"]),
        eligible_without_asset_row=int(survey["eligible_without_asset_row"]),
        queue_coverage_pct=float(survey["queue_coverage_pct"]),
        sync=sync_result,
    )
    tier_rows = session.exec(
        select(CatalogCoverAsset.priority_tier, func.count())
        .select_from(CatalogCoverAsset)
        .group_by(CatalogCoverAsset.priority_tier)
    ).all()
    for tier, count in tier_rows:
        report.by_tier[str(tier)] = int(count if not isinstance(count, tuple) else count[0])

    candidates = session.exec(
        select(CatalogCoverAsset)
        .where(CatalogCoverAsset.status.in_([COVER_ASSET_STATUS_PENDING, COVER_ASSET_STATUS_FAILED]))
        .order_by(CatalogCoverAsset.priority_score.asc(), CatalogCoverAsset.id.asc())
        .limit(pilot_limit * 3)
    ).all()
    work = [a for a in candidates if _retry_ready(a)][:pilot_limit]
    for asset in work:
        if asset.source_url:
            report.with_resolvable_url += 1
        else:
            report.without_url += 1
        if len(report.sample_issue_ids) < 20:
            report.sample_issue_ids.append(int(asset.catalog_issue_id))
    report.pilot_would_process = len(work)
    return report


def run_p104_hydration(
    session: Session,
    *,
    limit: int = 100,
    sync_limit: int = 0,
    dry_run: bool = False,
    reprocess: bool = False,
    download_workers: int | None = None,
    process_workers: int | None = None,
    downloads_per_minute: float | None = None,
    on_asset_processed: Callable[[int, CatalogCoverAsset, CatalogCoverHydrationRun, str], None] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    dw = max(1, int(download_workers if download_workers is not None else settings.p104_download_workers))
    pw = max(1, int(process_workers if process_workers is not None else settings.p104_process_workers))
    dpm = float(downloads_per_minute if downloads_per_minute is not None else settings.p104_downloads_per_minute)

    sync_result = sync_cover_assets_batch(session, sync_limit=sync_limit)
    run = _start_run(session, mode="dry_run" if dry_run else "hydrate", limit=limit)
    session.commit()

    candidates = session.exec(
        select(CatalogCoverAsset)
        .where(CatalogCoverAsset.status.in_([COVER_ASSET_STATUS_PENDING, COVER_ASSET_STATUS_FAILED]))
        .order_by(CatalogCoverAsset.priority_score.asc(), CatalogCoverAsset.id.asc())
        .limit(limit * 3)
    ).all()
    work = [a for a in candidates if _retry_ready(a)][:limit]
    run.queued = len(work)
    session.add(run)
    session.commit()

    perf = P104PerformanceSummary()
    rate_limiter = GlobalDownloadRateLimiter(dpm)
    wall_start = time.perf_counter()
    engine = session.get_bind()

    use_concurrency = not dry_run and (dw > 1 or pw > 1)

    run_id = int(run.id or 0)

    if use_concurrency:
        _run_p104_hydration_concurrent(
            engine,
            run,
            work,
            download_workers=dw,
            process_workers=pw,
            downloads_per_minute=dpm,
            reprocess=reprocess,
            perf=perf,
            on_asset_processed=on_asset_processed,
        )
    else:
        commits_since_flush = 0
        for index, asset in enumerate(work, start=1):
            timing: HydrateStageTiming | None = None
            t_asset = time.perf_counter()
            if not dry_run:
                timing = HydrateStageTiming()
            outcome = hydrate_cover_asset(
                session,
                asset,
                dry_run=dry_run,
                reprocess=reprocess,
                rate_limiter=rate_limiter if not dry_run else None,
                timing=timing,
                hydration_run_id=run_id if not dry_run else None,
            )
            if outcome == COVER_ASSET_STATUS_COMPLETE:
                run.completed += 1
                run.downloaded += 1
            elif outcome == COVER_ASSET_STATUS_SKIPPED_NO_URL:
                run.skipped_no_url += 1
            elif outcome == COVER_ASSET_STATUS_FAILED:
                run.failed += 1
            session.add(run)
            commits_since_flush += 1
            should_commit = commits_since_flush >= P104_SEQUENTIAL_COMMIT_EVERY or index == len(work)
            if should_commit:
                t_db = time.perf_counter()
                session.commit()
                if timing is not None:
                    timing.db_update_commit += time.perf_counter() - t_db
                commits_since_flush = 0
            elif timing is not None:
                t_db = time.perf_counter()
                session.flush()
                timing.db_update_commit += time.perf_counter() - t_db
            if timing is not None:
                timing.total = time.perf_counter() - t_asset
                perf.add(timing)
            if on_asset_processed is not None:
                on_asset_processed(index, asset, run, outcome)

    run = _reload_hydration_run(session, run_id)

    elapsed = time.perf_counter() - wall_start
    progress_summary = _hydration_progress_summary(
        run,
        elapsed_seconds=elapsed,
        download_workers=dw,
        process_workers=pw,
        downloads_per_minute=dpm,
    )

    summary = {
        "run_id": int(run.id or 0),
        "mode": run.mode,
        "limit": limit,
        "sync_limit": sync_limit,
        "sync": sync_result.to_dict(),
        "queued": run.queued,
        "downloaded": run.downloaded,
        "completed": run.completed,
        "failed": run.failed,
        "skipped_no_url": run.skipped_no_url,
        "dry_run": dry_run,
        "reprocess": reprocess,
        "download_workers": dw,
        "process_workers": pw,
        "downloads_per_minute": dpm,
        "queue_counts": asset_status_counts(session),
        "queue_counts_at": utc_now().isoformat(),
        "run_asset_complete_count": _count_assets_for_run(session, run_id),
        "progress": progress_summary,
        "performance": perf.to_dict(),
    }
    if not dry_run:
        _finish_run(session, run_id, log_payload=summary)
        session.commit()
        run = _reload_hydration_run(session, run_id)
        summary["log_path"] = run.log_path
    return summary


def _count_assets_for_run(session: Session, run_id: int) -> int:
    row = session.exec(
        select(func.count())
        .select_from(CatalogCoverAsset)
        .where(CatalogCoverAsset.last_hydration_run_id == int(run_id))
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE)
    ).one()
    return int(row[0] if isinstance(row, tuple) else row)


def _sync_run_counters_from_assets(session: Session, run_id: int) -> CatalogCoverHydrationRun:
    run = _reload_hydration_run(session, run_id)
    complete = session.exec(
        select(func.count())
        .select_from(CatalogCoverAsset)
        .where(CatalogCoverAsset.last_hydration_run_id == int(run_id))
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE)
    ).one()
    failed = session.exec(
        select(func.count())
        .select_from(CatalogCoverAsset)
        .where(CatalogCoverAsset.last_hydration_run_id == int(run_id))
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_FAILED)
    ).one()
    skipped = session.exec(
        select(func.count())
        .select_from(CatalogCoverAsset)
        .where(CatalogCoverAsset.last_hydration_run_id == int(run_id))
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_SKIPPED_NO_URL)
    ).one()
    run.completed = int(complete[0] if isinstance(complete, tuple) else complete)
    run.downloaded = run.completed
    run.failed = int(failed[0] if isinstance(failed, tuple) else failed)
    run.skipped_no_url = int(skipped[0] if isinstance(skipped, tuple) else skipped)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def reconcile_p104_hydration_run(
    session: Session,
    run_id: int,
    *,
    dry_run: bool = False,
    resync_run_counters: bool = True,
) -> dict[str, Any]:
    """Mark assets complete when on-disk derivatives exist; optionally fix run counters."""
    run = session.get(CatalogCoverHydrationRun, run_id)
    if run is None:
        raise ValueError(f"hydration run {run_id} not found")

    staging_root = P104_LOG_DIR / f"staging_run_{run_id}"
    candidate_ids: set[int] = set()
    if staging_root.is_dir():
        for path in staging_root.glob("*.bin"):
            if path.stem.isdigit():
                candidate_ids.add(int(path.stem))

    stale_statuses = (
        COVER_ASSET_STATUS_PENDING,
        COVER_ASSET_STATUS_DOWNLOADING,
        COVER_ASSET_STATUS_FAILED,
    )
    if candidate_ids:
        rows = session.exec(select(CatalogCoverAsset).where(CatalogCoverAsset.id.in_(candidate_ids))).all()
    else:
        rows = []

    repaired: list[int] = []
    already_ok: list[int] = []
    still_missing_files: list[int] = []

    for asset in rows:
        aid = int(asset.id or 0)
        if asset.status not in stale_statuses:
            if asset.status == COVER_ASSET_STATUS_COMPLETE and asset.last_hydration_run_id == run_id:
                already_ok.append(aid)
            continue
        if asset.medium_path and asset.original_path:
            ok, _missing = verify_asset_files(asset)
        else:
            base_dir = _asset_dir(session, int(asset.catalog_issue_id), aid)
            medium = base_dir / "medium.jpg"
            ok = medium.is_file()
            if ok and not dry_run:
                asset.medium_path = str(medium)
                orig = base_dir / "original.bin"
                if orig.is_file():
                    asset.original_path = str(orig)
        if not ok:
            still_missing_files.append(aid)
            continue
        if asset.status == COVER_ASSET_STATUS_COMPLETE and asset.last_hydration_run_id == run_id:
            already_ok.append(aid)
            continue
        if dry_run:
            repaired.append(aid)
            continue
        now = utc_now()
        asset.status = COVER_ASSET_STATUS_COMPLETE
        asset.last_hydration_run_id = int(run_id)
        asset.downloaded_at = asset.downloaded_at or now
        asset.verified_at = now
        asset.last_error = None
        asset.updated_at = now
        session.add(asset)
        repaired.append(aid)

    if not dry_run and repaired:
        session.commit()

    if resync_run_counters and not dry_run:
        run = _sync_run_counters_from_assets(session, run_id)
    elif resync_run_counters and dry_run:
        run = _reload_hydration_run(session, run_id)

    return {
        "run_id": run_id,
        "dry_run": dry_run,
        "candidate_asset_ids": len(candidate_ids),
        "repaired_asset_ids": repaired[:50],
        "repaired_count": len(repaired),
        "already_ok_count": len(already_ok),
        "still_missing_files_count": len(still_missing_files),
        "run_completed": int(run.completed),
        "run_downloaded": int(run.downloaded),
        "run_failed": int(run.failed),
        "run_skipped_no_url": int(run.skipped_no_url),
        "queue_counts": asset_status_counts(session),
    }


def p104_dashboard_metrics(session: Session) -> dict[str, Any]:
    survey = survey_catalog_cover_queue(session)
    counts = asset_status_counts(session)
    total = sum(counts.values())
    complete = int(counts.get(COVER_ASSET_STATUS_COMPLETE, 0))
    failed = int(counts.get(COVER_ASSET_STATUS_FAILED, 0))
    skipped = int(counts.get(COVER_ASSET_STATUS_SKIPPED_NO_URL, 0))
    pending = int(counts.get(COVER_ASSET_STATUS_PENDING, 0)) + int(counts.get(COVER_ASSET_STATUS_DOWNLOADING, 0))

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    rate = session.exec(
        select(func.count())
        .select_from(CatalogCoverAsset)
        .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE)
        .where(CatalogCoverAsset.verified_at >= one_hour_ago)
    ).one()
    rate_per_hour = int(rate[0] if isinstance(rate, tuple) else rate)
    eta_hours: float | None = None
    if rate_per_hour > 0 and pending > 0:
        eta_hours = round(pending / rate_per_hour, 1)

    return {
        "total": total,
        "complete": complete,
        "failed": failed,
        "skipped_no_url": skipped,
        "pending": pending,
        "rate_per_hour": rate_per_hour,
        "eta_hours": eta_hours,
        "storage_root": str(_cover_root()),
        "total_catalog_issues": survey["total_catalog_issues"],
        "eligible_catalog_issues": survey["eligible_with_catalog_image_url"],
        "asset_rows": survey["asset_rows"],
        "issues_with_asset_row": survey["issues_with_asset_row"],
        "queue_coverage_pct": survey["queue_coverage_pct"],
        "eligible_without_asset_row": survey["eligible_without_asset_row"],
        "eligible_with_url_not_queued": survey["eligible_with_url_not_queued"],
    }
