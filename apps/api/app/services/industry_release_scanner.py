from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import utc_now
from app.models.industry_release_scan import IndustryReleaseCandidate, IndustryReleaseScanRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.industry_publisher import IndustryPublisherRead
from app.schemas.industry_release_scan import IndustryReleaseScanRunRead
from app.services.industry_publisher_scan_config import included_publishers_for_scan
from app.services.lunar_issue_identity import classify_lunar_issue_row, normalize_lunar_issue_number
from app.services.metadata_enrichment import normalize_publisher_name
from app.services.recommendation_forward_window import issue_in_forward_recommendation_window

PROGRESS_BATCH_SIZE = 50
SLOW_STEP_SECONDS = 60.0


@dataclass(frozen=True)
class IndustryScanOptions:
    forward_window_only: bool = True
    progress_callback: Callable[[str], None] | None = None


def _log(options: IndustryScanOptions | None, message: str) -> None:
    if options is not None and options.progress_callback is not None:
        options.progress_callback(message)


@dataclass(frozen=True)
class LunarCatalogReleaseRow:
    release_id: int
    publisher: str
    series_name: str
    issue_number: str
    foc_date: date | None
    release_date: date | None
    variant_count: int


def _is_lunar_catalog_issue(release_uuid: str) -> bool:
    classification = classify_lunar_issue_row(release_uuid=release_uuid)
    return classification in {"canonical_lunar_issue", "legacy_flat_variant_issue"}


def _normalize_issue_label(value: str) -> str:
    return normalize_lunar_issue_number(value)


def load_lunar_catalog_releases(
    session: Session,
    *,
    owner_user_id: int,
    forward_window_only: bool = False,
) -> list[LunarCatalogReleaseRow]:
    variant_counts = dict(
        session.exec(
            select(ReleaseVariant.issue_id, func.count())
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .group_by(ReleaseVariant.issue_id)
        ).all()
    )
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseSeries.series_name.asc(), ReleaseIssue.issue_number.asc())
    ).all()
    out: list[LunarCatalogReleaseRow] = []
    for issue, series in rows:
        if issue.id is None or not _is_lunar_catalog_issue(issue.release_uuid):
            continue
        if forward_window_only and not issue_in_forward_recommendation_window(issue):
            continue
        out.append(
            LunarCatalogReleaseRow(
                release_id=int(issue.id),
                publisher=series.publisher.strip(),
                series_name=series.series_name.strip(),
                issue_number=_normalize_issue_label(issue.issue_number),
                foc_date=issue.foc_date,
                release_date=issue.release_date,
                variant_count=int(variant_counts.get(int(issue.id), 0)),
            )
        )
    return out


def resolve_industry_publisher(
    session: Session | None,
    *,
    publisher: str,
    active_publishers: list[IndustryPublisherRead],
) -> tuple[str, str] | None:
    raw = publisher.strip()
    if not raw or not active_publishers:
        return None
    canonical = normalize_publisher_name(raw, session=session).canonical_value or raw
    key = canonical.strip().lower()
    for pub in active_publishers:
        name_key = pub.publisher_name.strip().lower()
        code_key = pub.publisher_code.strip().lower()
        if key == name_key or key == code_key:
            return (pub.publisher_code, pub.publisher_name)
    for pub in active_publishers:
        name_key = pub.publisher_name.strip().lower()
        if key.startswith(name_key) or name_key.startswith(key):
            return (pub.publisher_code, pub.publisher_name)
    return None


def _scan_run_to_read(row: IndustryReleaseScanRun) -> IndustryReleaseScanRunRead:
    return IndustryReleaseScanRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        status=row.status,
        started_at=row.started_at.isoformat(),
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
        releases_scanned=int(row.releases_scanned),
        candidates_created=int(row.candidates_created),
        candidates_total=int(row.candidates_total),
        publishers_included=int(row.publishers_included),
        error_message=row.error_message or "",
        created_at=row.created_at.isoformat(),
    )


def scan_industry_releases(
    session: Session,
    *,
    owner_user_id: int,
    options: IndustryScanOptions | None = None,
    catalog: list[LunarCatalogReleaseRow] | None = None,
) -> IndustryReleaseScanRunRead:
    opts = options or IndustryScanOptions()
    active = included_publishers_for_scan(session, owner_user_id=owner_user_id)
    run = IndustryReleaseScanRun(
        owner_user_id=owner_user_id,
        status="RUNNING",
        publishers_included=len(active),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.id is not None

    created = 0
    processed = 0
    try:
        if catalog is None:
            catalog = load_lunar_catalog_releases(
                session,
                owner_user_id=owner_user_id,
                forward_window_only=opts.forward_window_only,
            )
        run.releases_scanned = len(catalog)
        _log(opts, f"step=scan_catalog rows={len(catalog)} forward_window={opts.forward_window_only}")

        existing_release_ids = {
            int(row.release_id)
            for row in session.exec(
                select(IndustryReleaseCandidate.release_id).where(
                    IndustryReleaseCandidate.scan_run_id == int(run.id)
                )
            ).all()
        }

        loop_started = time.monotonic()
        pending_commit = 0
        for row in catalog:
            processed += 1
            resolved = resolve_industry_publisher(None, publisher=row.publisher, active_publishers=active)
            if resolved is None:
                continue
            publisher_code, publisher_name = resolved
            if int(row.release_id) in existing_release_ids:
                continue
            candidate = IndustryReleaseCandidate(
                owner_user_id=owner_user_id,
                scan_run_id=int(run.id),
                release_id=int(row.release_id),
                publisher_code=publisher_code,
                publisher_name=publisher_name,
                series_name=row.series_name,
                issue_number=row.issue_number,
                foc_date=row.foc_date,
                release_date=row.release_date,
                variant_count=row.variant_count,
                monitoring_status="MONITOR",
            )
            session.add(candidate)
            existing_release_ids.add(int(row.release_id))
            created += 1
            pending_commit += 1
            if pending_commit >= 100:
                session.commit()
                pending_commit = 0

            if processed % PROGRESS_BATCH_SIZE == 0:
                batch_secs = time.monotonic() - loop_started
                _log(
                    opts,
                    f"step=scan_loop progress processed={processed}/{len(catalog)} "
                    f"candidates_created={created} batch_secs={batch_secs:.1f}",
                )
                if batch_secs >= SLOW_STEP_SECONDS:
                    _log(opts, f"SLOW LOOP (>{int(SLOW_STEP_SECONDS)}s): scan_loop batch took {batch_secs:.1f}s")
                loop_started = time.monotonic()

        if pending_commit > 0:
            session.commit()

        run.candidates_created = created
        run.candidates_total = len(existing_release_ids)
        run.status = "SUCCESS"
        run.completed_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        _log(opts, f"step=scan_complete candidates_created={created} releases_scanned={len(catalog)}")
    except Exception as exc:
        run.status = "FAILED"
        run.error_message = str(exc)[:2000]
        run.completed_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return _scan_run_to_read(run)

    return _scan_run_to_read(run)
