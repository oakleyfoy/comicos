"""Import ComicVine issues for P97 volume issue import queue rows."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import P97VolumeIssueImportQueue
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter, ComicVineImportStats
from app.services.p97_comicvine_import_diagnostics import log_import_event
from app.services.p97_comicvine_import_ledger import record_comicvine_import_requests
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget
from app.services.p97_requested_volume_import_service import (
    apply_volume_issue_import_result,
    wait_for_comicvine_budget,
)
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)
from app.services.p97_volume_issue_queue_priority import (
    LAUNCH_PRIORITY_TIERS,
    TIER_0_MANUAL,
    TIER_4_DEPRIORITIZED,
)

REQUEST_TYPE = "issue_queue_import"
LOGGER = logging.getLogger(__name__)

DEFAULT_EXCLUDED_TIERS: tuple[str, ...] = (TIER_0_MANUAL, TIER_4_DEPRIORITIZED)
STALE_RUNNING_MINUTES = 180


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_transient_stop_error(exc: BaseException | None = None, *, failures: list[str] | None = None) -> bool:
    if exc is not None:
        if isinstance(exc, ConnectionResetError):
            return True
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 10054:
            return True
        text = str(exc).lower()
        if "connection reset" in text or "forcibly closed" in text:
            return True
    for line in failures or []:
        lowered = line.lower()
        if "420" in lowered or "throttl" in lowered:
            return True
        if "connection reset" in lowered or "forcibly closed" in lowered:
            return True
    return False


def select_pending_volume_issue_imports(
    session: Session,
    *,
    tier: str | None = None,
    excluded_tiers: tuple[str, ...] = DEFAULT_EXCLUDED_TIERS,
    limit: int = 10,
) -> list[P97VolumeIssueImportQueue]:
    query = (
        select(P97VolumeIssueImportQueue)
        .where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
        .order_by(
            P97VolumeIssueImportQueue.priority_score.desc(),
            P97VolumeIssueImportQueue.missing_issue_count.desc(),
            P97VolumeIssueImportQueue.comicvine_volume_id.asc(),
        )
    )
    if tier:
        if tier not in LAUNCH_PRIORITY_TIERS:
            raise ValueError(f"Unknown launch_priority_tier: {tier}")
        query = query.where(P97VolumeIssueImportQueue.launch_priority_tier == tier)
    elif excluded_tiers:
        query = query.where(P97VolumeIssueImportQueue.launch_priority_tier.notin_(excluded_tiers))
    return list(session.exec(query.limit(max(1, int(limit)))).all())


def count_queue_rows_by_status(session: Session, *, status: str) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(P97VolumeIssueImportQueue)
            .where(P97VolumeIssueImportQueue.status == status)
        ).one()
    )


def count_actionable_pending(
    session: Session,
    *,
    tier: str | None = None,
    excluded_tiers: tuple[str, ...] = DEFAULT_EXCLUDED_TIERS,
) -> int:
    query = select(func.count()).select_from(P97VolumeIssueImportQueue).where(
        P97VolumeIssueImportQueue.status == STATUS_PENDING
    )
    if tier:
        query = query.where(P97VolumeIssueImportQueue.launch_priority_tier == tier)
    elif excluded_tiers:
        query = query.where(P97VolumeIssueImportQueue.launch_priority_tier.notin_(excluded_tiers))
    return int(session.exec(query).one())


def recover_stale_running_rows(
    session: Session,
    *,
    stale_minutes: int = STALE_RUNNING_MINUTES,
    verbose: bool = True,
) -> int:
    """Reset queue rows stuck in running with no live worker heartbeat."""
    cutoff = _utc_now() - timedelta(minutes=max(1, int(stale_minutes)))
    rows = session.exec(
        select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.status == STATUS_RUNNING)
    ).all()
    recovered = 0
    for row in rows:
        started = row.started_at or row.updated_at
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started is not None and started >= cutoff:
            continue
        row.status = STATUS_PENDING
        row.last_error = (row.last_error or "stale running row recovered")[:4000]
        row.updated_at = _utc_now()
        session.add(row)
        recovered += 1
        log_import_event(
            f"recovered stale running row volume_id={row.comicvine_volume_id} name={row.name!r}",
            enabled=verbose,
        )
    if recovered:
        session.commit()
    return recovered


def queue_import_idle(
    session: Session,
    *,
    tier: str | None = None,
    excluded_tiers: tuple[str, ...] = DEFAULT_EXCLUDED_TIERS,
) -> bool:
    """True when there is no running work and no pending rows for this import scope."""
    running = count_queue_rows_by_status(session, status=STATUS_RUNNING)
    pending = count_actionable_pending(session, tier=tier, excluded_tiers=excluded_tiers)
    return running == 0 and pending == 0


def mark_queue_row_running(session: Session, row: P97VolumeIssueImportQueue) -> P97VolumeIssueImportQueue:
    now = _utc_now()
    row.status = STATUS_RUNNING
    row.started_at = now
    row.updated_at = now
    row.attempts = int(row.attempts or 0) + 1
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def mark_queue_row_failed(
    session: Session,
    row: P97VolumeIssueImportQueue,
    *,
    error: str,
) -> P97VolumeIssueImportQueue:
    row.status = STATUS_FAILED
    row.last_error = error[:4000]
    row.updated_at = _utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@dataclass
class VolumeQueueImportItemResult:
    volume_id: int
    name: str
    launch_priority_tier: str
    dry_run: bool
    created_issues: int = 0
    updated_issues: int = 0
    api_requests_used: int = 0
    queue_status: str | None = None
    throttled: bool = False
    failures: list[str] = field(default_factory=list)


@dataclass
class VolumeQueueImportRunResult:
    dry_run: bool
    tier_filter: str | None
    limit_volumes: int
    volumes_selected: int = 0
    volumes_processed: int = 0
    volumes_complete: int = 0
    volumes_failed: int = 0
    volumes_pending: int = 0
    total_created_issues: int = 0
    total_updated_issues: int = 0
    total_api_requests: int = 0
    stopped_reason: str | None = None
    items: list[VolumeQueueImportItemResult] = field(default_factory=list)


def import_one_queue_volume(
    session: Session,
    budget: ComicVineRateBudget,
    importer: ComicVineCatalogImporter,
    row: P97VolumeIssueImportQueue,
    *,
    issues_limit: int | None = None,
    dry_run: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    verbose: bool = True,
    http_timeout: float | None = None,
) -> VolumeQueueImportItemResult:
    volume_id = int(row.comicvine_volume_id)
    item = VolumeQueueImportItemResult(
        volume_id=volume_id,
        name=row.name,
        launch_priority_tier=row.launch_priority_tier,
        dry_run=dry_run,
    )

    if not wait_for_comicvine_budget(
        budget,
        sleep_fn=sleep_fn,
        log_fn=lambda msg: log_import_event(msg, enabled=verbose),
        context=f"volume_id={volume_id}",
    ):
        item.throttled = True
        item.failures.append("ComicVine budget paused or timed out waiting for rate budget")
        return item

    if http_timeout is not None:
        importer.http_timeout = float(http_timeout)

    def _trace(phase: str, path: str, meta: dict) -> None:
        detail = " ".join(f"{key}={value}" for key, value in meta.items())
        log_import_event(f"ComicVine {phase} {path} {detail}".strip(), enabled=verbose)

    importer.request_trace = _trace

    queue_id: int | None = None
    if not dry_run:
        log_import_event(f"mark running volume_id={volume_id}", enabled=verbose)
        running_row = mark_queue_row_running(session, row)
        queue_id = int(running_row.id) if running_row.id is not None else None

    per_volume_limit = 100 if issues_limit is None else max(1, int(issues_limit))
    stats: ComicVineImportStats
    log_import_event(
        f"import_single_volume start volume_id={volume_id} issues_per_chunk={per_volume_limit}",
        enabled=verbose,
    )
    try:
        stats = importer.import_single_volume(
            session,
            comicvine_volume_id=volume_id,
            import_issues=True,
            issues_per_volume_limit=per_volume_limit,
        )
    except Exception as exc:  # noqa: BLE001
        stats = ComicVineImportStats(volume_id=volume_id)
        stats.failures.append(f"import_error:{exc}")
        if not is_transient_stop_error(exc):
            pass

    log_import_event(
        f"import_single_volume end volume_id={volume_id} "
        f"created={stats.created_issues} updated={stats.updated_issues} "
        f"api_requests={stats.api_requests_used} throttled={stats.throttled}",
        enabled=verbose,
    )

    item.api_requests_used = int(stats.api_requests_used or 0)
    item.created_issues = int(stats.created_issues or 0)
    item.updated_issues = int(stats.updated_issues or 0)
    item.throttled = bool(stats.throttled)
    item.failures = list(stats.failures or [])

    record_comicvine_import_requests(
        budget,
        request_type=REQUEST_TYPE,
        volume_id=volume_id,
        queue_id=queue_id,
        api_requests_used=item.api_requests_used,
        throttled=bool(stats.throttled),
    )

    if dry_run:
        return item

    transient_stop = is_transient_stop_error(failures=item.failures) and not item.throttled

    if stats.throttled:
        log_import_event(f"apply queue result (throttle) volume_id={volume_id}", enabled=verbose)
        updated = apply_volume_issue_import_result(
            session,
            volume_id=volume_id,
            stats=stats,
            dry_run=False,
        )
        if updated is not None:
            item.queue_status = updated.status
        return item

    if transient_stop:
        pending_row = session.exec(
            select(P97VolumeIssueImportQueue).where(
                P97VolumeIssueImportQueue.comicvine_volume_id == volume_id
            )
        ).first()
        if pending_row is not None:
            pending_row.status = STATUS_PENDING
            pending_row.last_error = "; ".join(item.failures[:3])[:4000] or "connection reset"
            pending_row.updated_at = _utc_now()
            session.add(pending_row)
            session.commit()
            session.refresh(pending_row)
            item.queue_status = pending_row.status
        return item

    if stats.failures and item.created_issues == 0 and item.updated_issues == 0:
        mark_queue_row_failed(session, row, error="; ".join(stats.failures[:5]))
        item.queue_status = STATUS_FAILED
        return item

    log_import_event(f"apply queue result volume_id={volume_id}", enabled=verbose)
    updated = apply_volume_issue_import_result(
        session,
        volume_id=volume_id,
        stats=stats,
        dry_run=False,
    )
    if updated is not None:
        item.queue_status = updated.status
    return item


def run_volume_issue_queue_import(
    session: Session,
    budget: ComicVineRateBudget,
    importer: ComicVineCatalogImporter,
    *,
    tier: str | None = None,
    limit_volumes: int = 10,
    issues_limit: int | None = None,
    dry_run: bool = False,
    stop_on_throttle: bool = True,
    max_api_requests: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    verbose: bool = True,
    http_timeout: float | None = None,
    recover_stale_running: bool = True,
) -> VolumeQueueImportRunResult:
    excluded = () if tier else DEFAULT_EXCLUDED_TIERS
    if recover_stale_running and not dry_run:
        recovered = recover_stale_running_rows(session, verbose=verbose)
        if recovered:
            log_import_event(f"recovered {recovered} stale running queue row(s)", enabled=verbose)

    if queue_import_idle(session, tier=tier, excluded_tiers=excluded):
        log_import_event("queue idle: no running rows and no pending work in scope; exiting", enabled=verbose)
        return VolumeQueueImportRunResult(
            dry_run=dry_run,
            tier_filter=tier,
            limit_volumes=limit_volumes,
            volumes_selected=0,
            stopped_reason="queue_idle",
        )

    rows = select_pending_volume_issue_imports(
        session,
        tier=tier,
        excluded_tiers=excluded,
        limit=limit_volumes,
    )
    result = VolumeQueueImportRunResult(
        dry_run=dry_run,
        tier_filter=tier,
        limit_volumes=limit_volumes,
        volumes_selected=len(rows),
    )
    log_import_event(
        f"selected {len(rows)} pending volume(s) tier={tier!r} limit_volumes={limit_volumes}",
        enabled=verbose,
    )
    if not rows:
        result.stopped_reason = "no_pending_in_batch"
        log_import_event("no pending volumes matched selection; exiting", enabled=verbose)
        return result

    api_budget = max_api_requests if max_api_requests is None else max(0, int(max_api_requests))
    api_used_run = 0

    for row in rows:
        if max_api_requests is not None and api_used_run >= api_budget:
            result.stopped_reason = "max_api_requests"
            break

        item = import_one_queue_volume(
            session,
            budget,
            importer,
            row,
            issues_limit=issues_limit,
            dry_run=dry_run,
            sleep_fn=sleep_fn,
            verbose=verbose,
            http_timeout=http_timeout,
        )
        result.items.append(item)
        result.volumes_processed += 1
        result.total_created_issues += item.created_issues
        result.total_updated_issues += item.updated_issues
        result.total_api_requests += item.api_requests_used
        api_used_run += item.api_requests_used

        if item.queue_status == STATUS_COMPLETE:
            result.volumes_complete += 1
        elif item.queue_status == STATUS_FAILED:
            result.volumes_failed += 1
        elif item.queue_status == STATUS_PENDING:
            result.volumes_pending += 1

        stop = False
        if item.throttled:
            result.stopped_reason = "throttle"
            stop = stop_on_throttle
        elif is_transient_stop_error(failures=item.failures):
            result.stopped_reason = "connection_reset"
            stop = stop_on_throttle

        if stop:
            break

    if queue_import_idle(session, tier=tier, excluded_tiers=excluded):
        log_import_event(
            "queue idle after batch: running=0 and no pending work in scope",
            enabled=verbose,
        )
        if result.stopped_reason is None:
            result.stopped_reason = "queue_idle"

    log_import_event("run complete; ready for final summary", enabled=verbose)
    return result
