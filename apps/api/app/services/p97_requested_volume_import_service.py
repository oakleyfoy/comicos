"""Import ComicVine issues for a manually requested P97 volume."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlmodel import Session, select

from app.models.catalog_p97 import P97VolumeIssueImportQueue
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter, ComicVineImportStats
from app.services.p97_comicvine_import_ledger import record_comicvine_import_requests
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
    volume_coverage_percent,
)
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)

REQUEST_TYPE = "manual_issue_import"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def wait_for_comicvine_budget(
    budget: ComicVineRateBudget,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_wait_seconds: float = 300.0,
) -> bool:
    if budget.should_pause_for_420():
        return False
    decision = budget.evaluate()
    if decision.allowed:
        return True
    wait = min(decision.seconds_until_next_request, max_wait_seconds)
    if wait > 0:
        sleep_fn(wait)
    return budget.evaluate().allowed


@dataclass
class RequestedVolumeImportResult:
    volume_id: int
    dry_run: bool
    throttled: bool = False
    api_requests_used: int = 0
    created_issues: int = 0
    updated_issues: int = 0
    failures: list[str] = field(default_factory=list)
    queue_status: str | None = None


def _refresh_queue_row_counts(session: Session, row: P97VolumeIssueImportQueue) -> None:
    indexes = build_catalog_coverage_indexes(session)
    existing = existing_issue_count_for_volume(
        volume_id=int(row.comicvine_volume_id),
        name=row.name,
        publisher=row.publisher,
        indexes=indexes,
    )
    count_of_issues = int(row.count_of_issues or 0)
    row.existing_issue_count = existing
    row.missing_issue_count = max(count_of_issues - existing, 0)
    row.coverage_percent = volume_coverage_percent(
        count_of_issues=count_of_issues,
        existing_issue_count=existing,
    )
    row.updated_at = _utc_now()
    session.add(row)


def mark_volume_issue_import_running(session: Session, *, volume_id: int) -> P97VolumeIssueImportQueue | None:
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == int(volume_id)
        )
    ).first()
    if row is None:
        return None
    now = _utc_now()
    row.status = STATUS_RUNNING
    row.started_at = now
    row.updated_at = now
    row.attempts = int(row.attempts or 0) + 1
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def apply_volume_issue_import_result(
    session: Session,
    *,
    volume_id: int,
    stats: ComicVineImportStats,
    dry_run: bool,
) -> P97VolumeIssueImportQueue | None:
    if dry_run:
        return None
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == int(volume_id)
        )
    ).first()
    if row is None:
        return None
    now = _utc_now()
    if stats.throttled:
        row.status = STATUS_PENDING
        row.last_error = "; ".join(stats.failures) if stats.failures else "ComicVine HTTP 420"
    elif stats.failures and stats.created_issues == 0 and stats.updated_issues == 0:
        row.status = STATUS_FAILED
        row.last_error = "; ".join(stats.failures[:5])
    else:
        _refresh_queue_row_counts(session, row)
        if row.missing_issue_count <= 0:
            row.status = STATUS_COMPLETE
            row.completed_at = now
        else:
            row.status = STATUS_PENDING
            row.last_error = None
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def import_requested_volume_issues(
    session: Session,
    budget: ComicVineRateBudget,
    importer: ComicVineCatalogImporter,
    *,
    volume_id: int,
    limit: int | None = None,
    dry_run: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> RequestedVolumeImportResult:
    volume_id = int(volume_id)
    result = RequestedVolumeImportResult(volume_id=volume_id, dry_run=dry_run)

    if not wait_for_comicvine_budget(budget, sleep_fn=sleep_fn):
        result.throttled = True
        result.failures.append("ComicVine budget paused for HTTP 420")
        return result

    queue_row = None if dry_run else mark_volume_issue_import_running(session, volume_id=volume_id)
    queue_id = int(queue_row.id) if queue_row and queue_row.id is not None else None

    per_volume_limit = 100 if limit is None else max(1, int(limit))
    stats = importer.import_single_volume(
        session,
        comicvine_volume_id=volume_id,
        import_issues=True,
        issues_per_volume_limit=per_volume_limit,
    )
    result.api_requests_used = int(stats.api_requests_used or 0)
    result.created_issues = int(stats.created_issues or 0)
    result.updated_issues = int(stats.updated_issues or 0)
    result.throttled = bool(stats.throttled)
    result.failures = list(stats.failures or [])

    record_comicvine_import_requests(
        budget,
        request_type=REQUEST_TYPE,
        volume_id=volume_id,
        queue_id=queue_id,
        api_requests_used=result.api_requests_used,
        throttled=result.throttled,
    )

    updated = apply_volume_issue_import_result(
        session,
        volume_id=volume_id,
        stats=stats,
        dry_run=dry_run,
    )
    if updated is not None:
        result.queue_status = updated.status
    return result
