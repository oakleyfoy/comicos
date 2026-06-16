"""P98-03/04 universe issue + variant shells."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogSeries
from app.models.universe import (
    DEFAULT_VARIANT_TYPE,
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UNIVERSE_VARIANT_STATUS_CATALOGED,
    UNIVERSE_VARIANT_STATUS_DISCOVERED,
    UniverseIssue,
    UniversePublisher,
    UniverseVariant,
    UniverseVolume,
)
from app.schemas.master_universe import (
    MasterUniverseIssueListResponse,
    MasterUniverseIssueNode,
    MasterUniverseVariantListResponse,
    MasterUniverseVariantNode,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series
from app.services.universe.universe_common import clamp_limit, clamp_offset

VOLUME_STATUS_BUILT = "built"
VOLUME_STATUS_VOLUME_ONLY = "VOLUME_ONLY"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_default_variant(session: Session, issue: UniverseIssue) -> tuple[UniverseVariant, bool]:
    """Return (variant, created) for the issue's UNKNOWN/STANDARD shell."""
    row = session.exec(
        select(UniverseVariant).where(
            UniverseVariant.issue_id == int(issue.id or 0),
            UniverseVariant.variant_type == DEFAULT_VARIANT_TYPE,
            UniverseVariant.variant_name == "",
        )
    ).first()
    if row is not None:
        return row, False
    row = UniverseVariant(
        issue_id=int(issue.id or 0),
        variant_type=DEFAULT_VARIANT_TYPE,
        variant_name="",
        status=UNIVERSE_VARIANT_STATUS_DISCOVERED,
    )
    session.add(row)
    session.flush()
    return row, True


def ensure_default_variant(session: Session, issue: UniverseIssue) -> UniverseVariant:
    row, _created = _ensure_default_variant(session, issue)
    return row


def upsert_issue_shell(
    session: Session,
    *,
    volume: UniverseVolume,
    issue_number: str,
    issue_title: str | None = None,
    cover_date=None,
    comicvine_issue_id: int | None = None,
    catalog_issue_id: int | None = None,
) -> UniverseIssue:
    norm = normalize_issue_number(issue_number)
    if not norm:
        raise ValueError("issue_number required")
    row = session.exec(
        select(UniverseIssue).where(
            UniverseIssue.volume_id == int(volume.id or 0),
            UniverseIssue.normalized_issue_number == norm,
        )
    ).first()
    status = UNIVERSE_ISSUE_STATUS_CATALOGED if catalog_issue_id else UNIVERSE_ISSUE_STATUS_DISCOVERED
    if row is None:
        row = UniverseIssue(
            volume_id=int(volume.id or 0),
            issue_number=issue_number.strip(),
            normalized_issue_number=norm,
            issue_title=issue_title,
            cover_date=cover_date,
            comicvine_issue_id=comicvine_issue_id,
            status=status,
        )
        session.add(row)
        session.flush()
    else:
        if issue_title:
            row.issue_title = issue_title
        if cover_date:
            row.cover_date = cover_date
        if comicvine_issue_id:
            row.comicvine_issue_id = comicvine_issue_id
        if catalog_issue_id:
            row.status = UNIVERSE_ISSUE_STATUS_CATALOGED
        row.updated_at = _utc_now()
        session.add(row)
        session.flush()

    variant = ensure_default_variant(session, row)
    if catalog_issue_id:
        variant.catalog_issue_id = catalog_issue_id
        variant.status = UNIVERSE_VARIANT_STATUS_CATALOGED
        variant.updated_at = _utc_now()
        session.add(variant)
    return row


@dataclass
class IssueShellBuildStats:
    """Mutable running totals for a P98 issue shell build."""

    selected_volumes: int = 0
    processed: int = 0
    skipped_existing: int = 0
    skipped_no_source: int = 0
    failed: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    failed_volume_ids: list[int] = field(default_factory=list)
    volume_only_ids: list[int] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def as_dict(self) -> dict:
        return {
            "selected_volumes": self.selected_volumes,
            "processed": self.processed,
            "skipped_existing": self.skipped_existing,
            "skipped_no_source": self.skipped_no_source,
            "failed": self.failed,
            "issues_created": self.issues_created,
            "issues_updated": self.issues_updated,
            "variants_created": self.variants_created,
            "variants_updated": self.variants_updated,
            "failed_volume_ids": list(self.failed_volume_ids),
            "volume_only_ids": list(self.volume_only_ids),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


def _build_catalog_source_index(session: Session) -> dict[int, list[int]]:
    """Map comicvine_volume_id -> [catalog_series_id, ...] in a single pass."""
    index: dict[int, list[int]] = defaultdict(list)
    for series in session.exec(select(CatalogSeries)).all():
        cv_key = comicvine_volume_id_for_series(series)
        if not cv_key or not str(cv_key).isdigit():
            continue
        if series.id is not None:
            index[int(cv_key)].append(int(series.id))
    return dict(index)


def _comicvine_issue_id(issue: CatalogIssue) -> int | None:
    bucket = (issue.external_source_ids or {}).get("COMICVINE")
    if isinstance(bucket, dict) and bucket:
        try:
            return int(next(iter(bucket.keys())))
        except (StopIteration, TypeError, ValueError):
            return None
    return None


def _volume_has_issue_shells(session: Session, volume_id: int) -> bool:
    return (
        session.exec(
            select(UniverseIssue.id).where(UniverseIssue.volume_id == volume_id).limit(1)
        ).first()
        is not None
    )


def _build_single_volume(
    session: Session,
    *,
    volume: UniverseVolume,
    source_series_ids: list[int],
    stats: IssueShellBuildStats,
) -> int:
    """Create issue + variant shells for one volume. Returns issues touched. Raises on DB error."""
    if not source_series_ids:
        return 0
    issues = session.exec(
        select(CatalogIssue).where(CatalogIssue.series_id.in_(source_series_ids))
    ).all()
    touched = 0
    for issue in issues:
        norm = normalize_issue_number(issue.issue_number)
        if not norm:
            continue
        existing_issue = session.exec(
            select(UniverseIssue).where(
                UniverseIssue.volume_id == int(volume.id or 0),
                UniverseIssue.normalized_issue_number == norm,
            )
        ).first()
        existing_variant = None
        if existing_issue is not None:
            existing_variant = session.exec(
                select(UniverseVariant).where(
                    UniverseVariant.issue_id == int(existing_issue.id or 0),
                    UniverseVariant.variant_type == DEFAULT_VARIANT_TYPE,
                    UniverseVariant.variant_name == "",
                )
            ).first()
        # upsert_issue_shell ensures the UNKNOWN/STANDARD variant exists, so we
        # decide created-vs-updated from the pre-call state (no double-create).
        upsert_issue_shell(
            session,
            volume=volume,
            issue_number=issue.issue_number,
            issue_title=issue.title,
            cover_date=issue.cover_date or issue.store_date or issue.release_date,
            comicvine_issue_id=_comicvine_issue_id(issue),
            catalog_issue_id=int(issue.id or 0) if issue.id else None,
        )
        if existing_issue is None:
            stats.issues_created += 1
        else:
            stats.issues_updated += 1
        if existing_variant is None:
            stats.variants_created += 1
        else:
            stats.variants_updated += 1
        touched += 1
    return touched


def _select_universe_volumes(
    session: Session,
    *,
    publisher: str | None,
    start_after_volume_id: int | None,
    limit_volumes: int | None,
) -> list[UniverseVolume]:
    stmt = select(UniverseVolume)
    if publisher and publisher.strip():
        pub_ids = [
            int(pid)
            for pid in session.exec(
                select(UniversePublisher.id).where(UniversePublisher.name.ilike(f"%{publisher.strip()}%"))
            ).all()
            if pid is not None
        ]
        if not pub_ids:
            return []
        stmt = stmt.where(UniverseVolume.publisher_id.in_(pub_ids))
    if start_after_volume_id is not None:
        stmt = stmt.where(UniverseVolume.comicvine_volume_id > int(start_after_volume_id))
    stmt = stmt.order_by(UniverseVolume.comicvine_volume_id.asc())
    if limit_volumes is not None and limit_volumes > 0:
        stmt = stmt.limit(int(limit_volumes))
    return list(session.exec(stmt).all())


def build_issue_shells(
    session: Session,
    *,
    limit_volumes: int | None = None,
    publisher: str | None = None,
    start_after_volume_id: int | None = None,
    commit_every: int = 25,
    dry_run: bool = False,
    refresh: bool = False,
    progress_every: int = 25,
    progress_callback: Callable[[IssueShellBuildStats, UniverseVolume], None] | None = None,
) -> IssueShellBuildStats:
    """Volume-driven issue/variant shell builder with resume + per-volume safety.

    Iterates ``universe_volume`` rows, maps each to local catalog source issues,
    and creates issue shells (each with an UNKNOWN/STANDARD variant). Volumes with
    no local source issues are flagged ``VOLUME_ONLY`` instead of hanging.
    """
    commit_every = max(1, int(commit_every))
    stats = IssueShellBuildStats()
    volumes = _select_universe_volumes(
        session,
        publisher=publisher,
        start_after_volume_id=start_after_volume_id,
        limit_volumes=limit_volumes,
    )
    stats.selected_volumes = len(volumes)
    if not volumes:
        return stats

    source_index = _build_catalog_source_index(session)
    pending_since_commit = 0
    progress_every = max(1, int(progress_every))
    seen = 0

    def _emit(volume: UniverseVolume, *, force: bool = False) -> None:
        if progress_callback is None:
            return
        if force or seen % progress_every == 0:
            progress_callback(stats, volume)

    for volume in volumes:
        seen += 1
        volume_id = int(volume.id or 0)
        cv_id = int(volume.comicvine_volume_id)

        if not refresh and _volume_has_issue_shells(session, volume_id):
            stats.skipped_existing += 1
            _emit(volume)
            continue

        source_series_ids = source_index.get(cv_id, [])
        if not source_series_ids:
            stats.skipped_no_source += 1
            stats.volume_only_ids.append(cv_id)
            if not dry_run and volume.volume_status != VOLUME_STATUS_VOLUME_ONLY:
                volume.volume_status = VOLUME_STATUS_VOLUME_ONLY
                volume.updated_at = _utc_now()
                session.add(volume)
                pending_since_commit += 1
            _emit(volume)
            continue

        try:
            nested = session.begin_nested()
            try:
                _build_single_volume(
                    session,
                    volume=volume,
                    source_series_ids=source_series_ids,
                    stats=stats,
                )
                if not dry_run and volume.volume_status != VOLUME_STATUS_BUILT:
                    volume.volume_status = VOLUME_STATUS_BUILT
                    volume.updated_at = _utc_now()
                    session.add(volume)
                if dry_run:
                    # Discard the volume's work; in-memory stats are preserved.
                    nested.rollback()
                else:
                    nested.commit()
            except Exception:
                nested.rollback()
                raise
        except Exception:  # noqa: BLE001 - one bad volume must not abort the run
            stats.failed += 1
            stats.failed_volume_ids.append(cv_id)
            _emit(volume, force=True)
            continue

        stats.processed += 1
        if not dry_run:
            pending_since_commit += 1
            if pending_since_commit >= commit_every:
                session.commit()
                pending_since_commit = 0

        _emit(volume)

    if dry_run:
        session.rollback()
    elif pending_since_commit > 0:
        session.commit()
    return stats


def build_issue_shells_from_catalog(session: Session) -> dict[str, int]:
    """Backward-compatible wrapper: build all volumes once (no refresh)."""
    stats = build_issue_shells(session)
    return {
        "issues_created": stats.issues_created,
        "issues_updated": stats.issues_updated,
        "variants_linked": stats.variants_created + stats.variants_updated,
        "skipped_no_source": stats.skipped_no_source,
        "failed": stats.failed,
    }


def list_issues_for_volume(
    session: Session,
    *,
    volume_id: int,
    issue_number: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseIssueListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    volume = session.get(UniverseVolume, volume_id)
    if volume is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volume not found")

    stmt = select(UniverseIssue).where(UniverseIssue.volume_id == volume_id)
    if issue_number and issue_number.strip():
        needle = issue_number.strip()
        stmt = stmt.where(
            (UniverseIssue.issue_number.ilike(f"%{needle}%"))
            | (UniverseIssue.normalized_issue_number.ilike(f"%{needle}%"))
        )
    rows = list(session.exec(stmt.order_by(UniverseIssue.normalized_issue_number.asc())).all())
    var_counts = {
        int(iid): int(cnt)
        for iid, cnt in session.exec(
            select(UniverseVariant.issue_id, func.count(UniverseVariant.id)).group_by(UniverseVariant.issue_id)
        ).all()
    }
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniverseIssueNode(
            id=int(row.id or 0),
            issue_number=row.issue_number,
            normalized_issue_number=row.normalized_issue_number,
            issue_title=row.issue_title,
            cover_date=row.cover_date,
            comicvine_issue_id=row.comicvine_issue_id,
            status=row.status,
            variant_count=var_counts.get(int(row.id or 0), 0),
        )
        for row in page
    ]
    return MasterUniverseIssueListResponse(
        volume_id=volume_id,
        volume_name=volume.name,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def list_variants_for_issue(
    session: Session,
    *,
    issue_id: int,
    limit: int | None = None,
    offset: int | None = None,
) -> MasterUniverseVariantListResponse:
    limit = clamp_limit(limit)
    offset = clamp_offset(offset)
    issue = session.get(UniverseIssue, issue_id)
    if issue is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    ensure_default_variant(session, issue)
    session.flush()

    rows = list(
        session.exec(
            select(UniverseVariant)
            .where(UniverseVariant.issue_id == issue_id)
            .order_by(UniverseVariant.id.asc())
        ).all()
    )
    total_count = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MasterUniverseVariantNode(
            id=int(row.id or 0),
            variant_type=row.variant_type,
            variant_name=row.variant_name,
            status=row.status,
            catalog_issue_id=row.catalog_issue_id,
            comicvine_variant_id=row.comicvine_variant_id,
            is_unknown_shell=row.variant_type == DEFAULT_VARIANT_TYPE and not row.variant_name,
        )
        for row in page
    ]
    return MasterUniverseVariantListResponse(
        issue_id=issue_id,
        issue_number=issue.issue_number,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
