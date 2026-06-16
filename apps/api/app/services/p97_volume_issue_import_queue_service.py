"""Build and report the P97 volume issue import queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
    volume_coverage_percent,
)
from app.services.p97_volume_issue_queue_priority import (
    LAUNCH_PRIORITY_TIERS,
    TIER_0_MANUAL,
    compute_volume_import_priority,
)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

QUEUE_STATUSES = (
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_SKIPPED,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BuildVolumeIssueQueueResult:
    discovered_volumes_scanned: int = 0
    queue_rows_inserted: int = 0
    queue_rows_updated: int = 0
    skipped_complete: int = 0
    skipped_protected: int = 0
    removed_fully_covered: int = 0
    pending_priorities_refreshed: int = 0
    pending_queue_size: int = 0
    total_missing_issues_queued: int = 0


def _start_year_by_volume_id(session: Session, volume_ids: list[int]) -> dict[int, int | None]:
    if not volume_ids:
        return {}
    pairs = session.exec(
        select(ComicVineVolumeUniverse.volume_id, ComicVineVolumeUniverse.start_year).where(
            ComicVineVolumeUniverse.volume_id.in_(volume_ids)
        )
    ).all()
    return {int(vid): (int(sy) if sy is not None else None) for vid, sy in pairs}


def refresh_pending_queue_priorities(session: Session) -> int:
    """Recompute tier/score for pending and failed rows (never manual tier_0)."""
    updated = 0
    rows = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.status.in_((STATUS_PENDING, STATUS_FAILED))
        )
    ).all()
    start_years = _start_year_by_volume_id(
        session, [int(r.comicvine_volume_id) for r in rows]
    )
    for row in rows:
        if row.launch_priority_tier == TIER_0_MANUAL:
            continue
        priority = compute_volume_import_priority(
            missing_issue_count=int(row.missing_issue_count or 0),
            count_of_issues=int(row.count_of_issues or 0),
            coverage_percent=float(row.coverage_percent or 0.0),
            publisher=row.publisher,
            name=row.name,
            start_year=start_years.get(int(row.comicvine_volume_id)),
        )
        if (
            row.priority_score != priority.priority_score
            or row.launch_priority_tier != priority.launch_priority_tier
        ):
            row.priority_score = priority.priority_score
            row.launch_priority_tier = priority.launch_priority_tier
            row.updated_at = _utc_now()
            session.add(row)
            updated += 1
    if updated:
        session.commit()
    return updated


@dataclass(frozen=True)
class VolumeIssueQueueReport:
    pending: int
    running: int
    complete: int
    failed: int
    skipped: int
    total_missing_issues_queued: int
    top_volumes: list[P97VolumeIssueImportQueue]
    top_volumes_by_tier: dict[str, list[P97VolumeIssueImportQueue]]
    top_publishers: list[tuple[str, int, int]]


def build_volume_issue_import_queue(
    session: Session,
    *,
    refresh_complete: bool = False,
) -> BuildVolumeIssueQueueResult:
    result = BuildVolumeIssueQueueResult()
    indexes = build_catalog_coverage_indexes(session)
    universe_rows = session.exec(select(ComicVineVolumeUniverse)).all()
    result.discovered_volumes_scanned = len(universe_rows)

    protected_without_refresh = {STATUS_RUNNING}
    if not refresh_complete:
        protected_without_refresh.add(STATUS_COMPLETE)

    for universe in universe_rows:
        volume_id = int(universe.volume_id)
        count_of_issues = int(universe.count_of_issues or 0)
        existing = existing_issue_count_for_volume(
            volume_id=volume_id,
            name=universe.name,
            publisher=universe.publisher,
            indexes=indexes,
        )
        missing = max(count_of_issues - existing, 0)
        coverage = volume_coverage_percent(
            count_of_issues=count_of_issues,
            existing_issue_count=existing,
        )

        existing_row = session.exec(
            select(P97VolumeIssueImportQueue).where(
                P97VolumeIssueImportQueue.comicvine_volume_id == volume_id
            )
        ).first()

        if missing <= 0:
            result.skipped_complete += 1
            if existing_row is not None:
                if existing_row.launch_priority_tier == TIER_0_MANUAL:
                    result.skipped_protected += 1
                    continue
                if existing_row.status == STATUS_PENDING:
                    session.delete(existing_row)
                    session.commit()
                    result.removed_fully_covered += 1
            continue

        if existing_row is not None and existing_row.launch_priority_tier == TIER_0_MANUAL:
            if existing_row.status == STATUS_COMPLETE and not refresh_complete:
                result.skipped_protected += 1
                continue
            existing = existing_issue_count_for_volume(
                volume_id=volume_id,
                name=universe.name,
                publisher=universe.publisher,
                indexes=indexes,
            )
            missing = max(count_of_issues - existing, 0)
            coverage = volume_coverage_percent(
                count_of_issues=count_of_issues,
                existing_issue_count=existing,
            )
            existing_row.name = universe.name
            existing_row.publisher = universe.publisher
            existing_row.count_of_issues = count_of_issues
            existing_row.existing_issue_count = existing
            existing_row.missing_issue_count = missing
            existing_row.coverage_percent = coverage
            existing_row.updated_at = _utc_now()
            session.add(existing_row)
            result.queue_rows_updated += 1
            continue

        if existing_row is not None and existing_row.status in protected_without_refresh:
            result.skipped_protected += 1
            continue

        priority = compute_volume_import_priority(
            missing_issue_count=missing,
            count_of_issues=count_of_issues,
            coverage_percent=coverage,
            publisher=universe.publisher,
            name=universe.name,
            start_year=universe.start_year,
        )
        now = _utc_now()
        if existing_row is None:
            session.add(
                P97VolumeIssueImportQueue(
                    comicvine_volume_id=volume_id,
                    name=universe.name,
                    publisher=universe.publisher,
                    count_of_issues=count_of_issues,
                    existing_issue_count=existing,
                    missing_issue_count=missing,
                    coverage_percent=coverage,
                    priority_score=priority.priority_score,
                    launch_priority_tier=priority.launch_priority_tier,
                    status=STATUS_PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
            result.queue_rows_inserted += 1
        else:
            existing_row.name = universe.name
            existing_row.publisher = universe.publisher
            existing_row.count_of_issues = count_of_issues
            existing_row.existing_issue_count = existing
            existing_row.missing_issue_count = missing
            existing_row.coverage_percent = coverage
            existing_row.priority_score = priority.priority_score
            existing_row.launch_priority_tier = priority.launch_priority_tier
            if refresh_complete and existing_row.status == STATUS_COMPLETE:
                existing_row.status = STATUS_PENDING
                existing_row.completed_at = None
            existing_row.updated_at = now
            session.add(existing_row)
            result.queue_rows_updated += 1

    session.commit()
    result.pending_priorities_refreshed = refresh_pending_queue_priorities(session)

    result.pending_queue_size = int(
        session.exec(
            select(func.count())
            .select_from(P97VolumeIssueImportQueue)
            .where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
        ).one()
    )
    result.total_missing_issues_queued = int(
        session.exec(
            select(func.coalesce(func.sum(P97VolumeIssueImportQueue.missing_issue_count), 0))
            .select_from(P97VolumeIssueImportQueue)
            .where(
                P97VolumeIssueImportQueue.status.in_(
                    (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED)
                )
            )
        ).one()
    )
    return result


def get_top_queued_volumes(
    session: Session,
    *,
    limit: int = 25,
    statuses: tuple[str, ...] = (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED),
) -> list[P97VolumeIssueImportQueue]:
    return list(
        session.exec(
            select(P97VolumeIssueImportQueue)
            .where(P97VolumeIssueImportQueue.status.in_(statuses))
            .order_by(
                P97VolumeIssueImportQueue.priority_score.desc(),
                P97VolumeIssueImportQueue.missing_issue_count.desc(),
                P97VolumeIssueImportQueue.comicvine_volume_id.asc(),
            )
            .limit(max(1, int(limit)))
        ).all()
    )


def get_top_queued_volumes_by_tier(
    session: Session,
    *,
    limit_per_tier: int = 10,
    statuses: tuple[str, ...] = (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED),
) -> dict[str, list[P97VolumeIssueImportQueue]]:
    grouped: dict[str, list[P97VolumeIssueImportQueue]] = {tier: [] for tier in LAUNCH_PRIORITY_TIERS}
    rows = session.exec(
        select(P97VolumeIssueImportQueue)
        .where(P97VolumeIssueImportQueue.status.in_(statuses))
        .order_by(
            P97VolumeIssueImportQueue.priority_score.desc(),
            P97VolumeIssueImportQueue.missing_issue_count.desc(),
            P97VolumeIssueImportQueue.comicvine_volume_id.asc(),
        )
    ).all()
    for row in rows:
        tier = row.launch_priority_tier or "tier_3_other_us"
        bucket = grouped.setdefault(tier, [])
        if len(bucket) < max(1, int(limit_per_tier)):
            bucket.append(row)
    return grouped


def get_volume_issue_queue_report(session: Session, *, top_limit: int = 25) -> VolumeIssueQueueReport:
    counts = {
        status: int(
            session.exec(
                select(func.count())
                .select_from(P97VolumeIssueImportQueue)
                .where(P97VolumeIssueImportQueue.status == status)
            ).one()
        )
        for status in QUEUE_STATUSES
    }
    total_missing = int(
        session.exec(
            select(func.coalesce(func.sum(P97VolumeIssueImportQueue.missing_issue_count), 0))
            .select_from(P97VolumeIssueImportQueue)
            .where(
                P97VolumeIssueImportQueue.status.in_(
                    (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED)
                )
            )
        ).one()
    )
    top_volumes = get_top_queued_volumes(session, limit=top_limit)
    top_volumes_by_tier = get_top_queued_volumes_by_tier(session, limit_per_tier=10)

    pub_rows = session.exec(
        select(
            P97VolumeIssueImportQueue.publisher,
            func.count(),
            func.coalesce(func.sum(P97VolumeIssueImportQueue.missing_issue_count), 0),
        )
        .where(P97VolumeIssueImportQueue.status.in_((STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED)))
        .group_by(P97VolumeIssueImportQueue.publisher)
    ).all()
    top_publishers: list[tuple[str, int, int]] = []
    for publisher, volume_count, missing_sum in pub_rows:
        label = (publisher or "").strip() or "Unknown"
        top_publishers.append((label, int(volume_count), int(missing_sum)))
    top_publishers.sort(key=lambda row: (-row[2], row[0]))

    return VolumeIssueQueueReport(
        pending=counts[STATUS_PENDING],
        running=counts[STATUS_RUNNING],
        complete=counts[STATUS_COMPLETE],
        failed=counts[STATUS_FAILED],
        skipped=counts[STATUS_SKIPPED],
        total_missing_issues_queued=total_missing,
        top_volumes=top_volumes,
        top_volumes_by_tier=top_volumes_by_tier,
        top_publishers=top_publishers,
    )
