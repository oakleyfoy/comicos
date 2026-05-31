from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace_publish import (
    MarketplacePublishJob,
    MarketplacePublishTarget,
    MarketplacePublishValidationIssue,
)
from app.schemas.marketplace_publish import (
    MarketplacePublishEventRead,
    MarketplacePublishJobDetail,
    MarketplacePublishJobListResponse,
    MarketplacePublishJobRead,
    MarketplacePublishRequest,
    MarketplacePublishTargetRead,
    MarketplacePublishValidationIssueRead,
)
from app.services.marketplace_publish_events import (
    log_job_completed,
    log_job_created,
    log_job_failed,
    log_job_ready,
    log_plan_created,
    log_validation_failed,
)
from app.services.marketplace_publish_planner import build_publish_plan
from app.services.marketplace_publish_validation import validate_publish_request

JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_VALIDATING = "VALIDATING"
JOB_STATUS_PLANNED = "PLANNED"
JOB_STATUS_READY = "READY"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"

TARGET_STATUS_PENDING = "PENDING"
TARGET_STATUS_PLANNED = "PLANNED"
TARGET_STATUS_SKIPPED = "SKIPPED"
TARGET_STATUS_COMPLETED = "COMPLETED"
TARGET_STATUS_FAILED = "FAILED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _job_read(row: MarketplacePublishJob) -> MarketplacePublishJobRead:
    return MarketplacePublishJobRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        listing_id=row.listing_id,
        job_uuid=row.job_uuid,
        status=row.status,
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
        created_at=row.created_at,
    )


def _target_read(row: MarketplacePublishTarget) -> MarketplacePublishTargetRead:
    return MarketplacePublishTargetRead(
        id=int(row.id or 0),
        publish_job_id=row.publish_job_id,
        marketplace_id=row.marketplace_id,
        marketplace_account_id=row.marketplace_account_id,
        listing_mapping_id=row.listing_mapping_id,
        target_status=row.target_status,
        planned_payload_json=dict(row.planned_payload_json or {}),
        result_payload_json=dict(row.result_payload_json or {}) if row.result_payload_json is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event_reads(session: Session, *, publish_job_id: int) -> list[MarketplacePublishEventRead]:
    from app.models.marketplace_publish import MarketplacePublishEvent

    rows = session.exec(
        select(MarketplacePublishEvent)
        .where(MarketplacePublishEvent.publish_job_id == publish_job_id)
        .order_by(MarketplacePublishEvent.created_at.asc(), MarketplacePublishEvent.id.asc())
    ).all()
    return [
        MarketplacePublishEventRead(
            id=int(row.id or 0),
            publish_job_id=row.publish_job_id,
            event_type=row.event_type,
            event_payload_json=dict(row.event_payload_json or {}),
            created_at=row.created_at,
        )
        for row in rows
    ]


def _issue_reads(session: Session, *, publish_job_id: int) -> list[MarketplacePublishValidationIssueRead]:
    rows = session.exec(
        select(MarketplacePublishValidationIssue)
        .where(MarketplacePublishValidationIssue.publish_job_id == publish_job_id)
        .order_by(MarketplacePublishValidationIssue.created_at.asc(), MarketplacePublishValidationIssue.id.asc())
    ).all()
    return [
        MarketplacePublishValidationIssueRead(
            id=int(row.id or 0),
            publish_job_id=row.publish_job_id,
            issue_code=row.issue_code,
            issue_message=row.issue_message,
            severity=row.severity,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _target_rows(session: Session, *, publish_job_id: int) -> list[MarketplacePublishTarget]:
    return session.exec(
        select(MarketplacePublishTarget)
        .where(MarketplacePublishTarget.publish_job_id == publish_job_id)
        .order_by(MarketplacePublishTarget.created_at.asc(), MarketplacePublishTarget.id.asc())
    ).all()


def _detail(session: Session, row: MarketplacePublishJob) -> MarketplacePublishJobDetail:
    publish_job_id = int(row.id or 0)
    return MarketplacePublishJobDetail(
        job=_job_read(row),
        targets=[_target_read(target) for target in _target_rows(session, publish_job_id=publish_job_id)],
        events=_event_reads(session, publish_job_id=publish_job_id),
        validation_issues=_issue_reads(session, publish_job_id=publish_job_id),
    )


def _job_or_404(session: Session, *, job_id: int) -> MarketplacePublishJob:
    row = session.get(MarketplacePublishJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace publish job not found.")
    return row


def _owner_job_or_404(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishJob:
    row = _job_or_404(session, job_id=job_id)
    if row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace publish job not found.")
    return row


def _target_or_404(session: Session, *, publish_job_id: int, target_id: int) -> MarketplacePublishTarget:
    row = session.get(MarketplacePublishTarget, target_id)
    if row is None or row.publish_job_id != publish_job_id:
        raise HTTPException(status_code=404, detail="Marketplace publish target not found.")
    return row


def _append_validation_issues(session: Session, *, publish_job_id: int, issues) -> None:
    now = utc_now()
    for issue in issues:
        session.add(
            MarketplacePublishValidationIssue(
                publish_job_id=publish_job_id,
                issue_code=issue.issue_code,
                issue_message=issue.issue_message,
                severity=issue.severity,
                created_at=now,
            )
        )


def create_publish_targets(session: Session, *, publish_job_id: int, payload: MarketplacePublishRequest) -> None:
    now = utc_now()
    for target in payload.targets:
        session.add(
            MarketplacePublishTarget(
                publish_job_id=publish_job_id,
                marketplace_id=target.marketplace_id,
                marketplace_account_id=target.marketplace_account_id,
                listing_mapping_id=None,
                target_status=TARGET_STATUS_PENDING,
                planned_payload_json={},
                result_payload_json=None,
                created_at=now,
                updated_at=now,
            )
        )
    session.flush()


def create_publish_job(session: Session, *, owner_id: int, requested_by: int, payload: MarketplacePublishRequest) -> MarketplacePublishJobDetail:
    now = utc_now()
    row = MarketplacePublishJob(
        owner_id=owner_id,
        listing_id=payload.listing_id,
        status=JOB_STATUS_PENDING,
        requested_by=requested_by,
        requested_at=now,
        started_at=None,
        completed_at=None,
        duration_ms=None,
        created_at=now,
    )
    session.add(row)
    session.flush()
    create_publish_targets(session, publish_job_id=int(row.id or 0), payload=payload)
    log_job_created(session, publish_job_id=int(row.id or 0), listing_id=payload.listing_id, requested_by=requested_by)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def list_publish_jobs(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplacePublishJobListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplacePublishJob)
        .where(MarketplacePublishJob.owner_id == owner_id)
        .order_by(MarketplacePublishJob.created_at.asc(), MarketplacePublishJob.id.asc())
    ).all()
    items = [_job_read(row) for row in rows]
    return MarketplacePublishJobListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def rebuild_publish_request(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishRequest:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    targets = _target_rows(session, publish_job_id=job_id)
    return MarketplacePublishRequest(
        listing_id=row.listing_id,
        targets=[
            {"marketplace_id": target.marketplace_id, "marketplace_account_id": target.marketplace_account_id}
            for target in targets
        ],
    )


def get_publish_job(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    return _detail(session, row)


def start_publish_job(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    if row.status not in {JOB_STATUS_PENDING, JOB_STATUS_FAILED, JOB_STATUS_VALIDATING}:
        raise HTTPException(status_code=409, detail="Publish job cannot enter validation from its current state.")
    row.status = JOB_STATUS_VALIDATING
    row.started_at = row.started_at or utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def validate_job_request(
    session: Session,
    *,
    owner_id: int,
    job_id: int,
    payload: MarketplacePublishRequest,
) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    if row.listing_id != payload.listing_id:
        raise HTTPException(status_code=422, detail="Publish request listing does not match the job listing.")
    if row.status == JOB_STATUS_COMPLETED:
        raise HTTPException(status_code=409, detail="Completed publish jobs cannot be revalidated.")
    row.status = JOB_STATUS_VALIDATING
    row.started_at = row.started_at or utc_now()
    session.add(row)
    issues = validate_publish_request(session, owner_id=owner_id, payload=payload)
    if issues:
        _append_validation_issues(session, publish_job_id=job_id, issues=issues)
        row.status = JOB_STATUS_FAILED
        row.completed_at = utc_now()
        row.duration_ms = max(int((_as_utc(row.completed_at) - _as_utc(row.started_at)).total_seconds() * 1000), 0)
        session.add(row)
        log_validation_failed(session, publish_job_id=job_id, issue_count=len(issues))
        log_job_failed(session, publish_job_id=job_id, reason="validation_failed")
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def mark_target_planned(
    session: Session,
    *,
    owner_id: int,
    job_id: int,
    target_id: int,
    planned_payload_json: dict,
    listing_mapping_id: int | None,
) -> MarketplacePublishTargetRead:
    _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    row = _target_or_404(session, publish_job_id=job_id, target_id=target_id)
    row.target_status = TARGET_STATUS_PLANNED
    row.planned_payload_json = planned_payload_json
    row.listing_mapping_id = listing_mapping_id
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return _target_read(row)


def mark_target_skipped(session: Session, *, owner_id: int, job_id: int, target_id: int, reason: str | None = None) -> MarketplacePublishTargetRead:
    _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    row = _target_or_404(session, publish_job_id=job_id, target_id=target_id)
    row.target_status = TARGET_STATUS_SKIPPED
    row.result_payload_json = {"reason": reason or ""}
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return _target_read(row)


def mark_target_completed(session: Session, *, owner_id: int, job_id: int, target_id: int, result_payload_json: dict | None = None) -> MarketplacePublishTargetRead:
    _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    row = _target_or_404(session, publish_job_id=job_id, target_id=target_id)
    row.target_status = TARGET_STATUS_COMPLETED
    row.result_payload_json = result_payload_json or {}
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return _target_read(row)


def mark_target_failed(session: Session, *, owner_id: int, job_id: int, target_id: int, reason: str | None = None) -> MarketplacePublishTargetRead:
    _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    row = _target_or_404(session, publish_job_id=job_id, target_id=target_id)
    row.target_status = TARGET_STATUS_FAILED
    row.result_payload_json = {"reason": reason or ""}
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return _target_read(row)


def plan_publish_job(
    session: Session,
    *,
    owner_id: int,
    job_id: int,
    payload: MarketplacePublishRequest,
) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    if row.status == JOB_STATUS_COMPLETED:
        raise HTTPException(status_code=409, detail="Completed publish jobs cannot be replanned.")
    issues = validate_publish_request(session, owner_id=owner_id, payload=payload)
    if issues:
        _append_validation_issues(session, publish_job_id=job_id, issues=issues)
        row.status = JOB_STATUS_FAILED
        row.completed_at = utc_now()
        row.duration_ms = max(int((_as_utc(row.completed_at) - _as_utc(row.started_at or row.requested_at)).total_seconds() * 1000), 0)
        session.add(row)
        log_validation_failed(session, publish_job_id=job_id, issue_count=len(issues))
        log_job_failed(session, publish_job_id=job_id, reason="planning_validation_failed")
        session.commit()
        session.refresh(row)
        return _detail(session, row)

    plan = build_publish_plan(session, owner_id=owner_id, payload=payload)
    targets = _target_rows(session, publish_job_id=job_id)
    if len(plan) != len(targets):
        raise HTTPException(status_code=409, detail="Publish target count does not match the stored job targets.")
    for target_row, planned in zip(targets, plan):
        mark_target_planned(
            session,
            owner_id=owner_id,
            job_id=job_id,
            target_id=int(target_row.id or 0),
            planned_payload_json=planned["planned_payload_json"],
            listing_mapping_id=planned["listing_mapping_id"],
        )
    row.status = JOB_STATUS_PLANNED
    session.add(row)
    log_plan_created(session, publish_job_id=job_id, target_count=len(plan))
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def ready_publish_job(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    targets = _target_rows(session, publish_job_id=job_id)
    if any(target.target_status == TARGET_STATUS_PENDING for target in targets):
        raise HTTPException(status_code=409, detail="Publish job cannot be marked ready while targets remain pending.")
    row.status = JOB_STATUS_READY
    session.add(row)
    log_job_ready(session, publish_job_id=job_id)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def complete_publish_job(session: Session, *, owner_id: int, job_id: int) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    targets = _target_rows(session, publish_job_id=job_id)
    if any(target.target_status == TARGET_STATUS_FAILED for target in targets):
        raise HTTPException(status_code=409, detail="Publish job cannot be completed while targets have failed.")
    if any(target.target_status == TARGET_STATUS_PENDING for target in targets):
        raise HTTPException(status_code=409, detail="Publish job can only complete after all targets are completed or skipped.")
    for target in targets:
        if target.target_status == TARGET_STATUS_PLANNED:
            mark_target_skipped(
                session,
                owner_id=owner_id,
                job_id=job_id,
                target_id=int(target.id or 0),
                reason="connector_execution_not_implemented",
            )
    row.status = JOB_STATUS_COMPLETED
    row.completed_at = utc_now()
    baseline = row.started_at or row.requested_at
    row.duration_ms = max(int((_as_utc(row.completed_at) - _as_utc(baseline)).total_seconds() * 1000), 0)
    session.add(row)
    log_job_completed(session, publish_job_id=job_id)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def fail_publish_job(session: Session, *, owner_id: int, job_id: int, reason: str | None = None) -> MarketplacePublishJobDetail:
    row = _owner_job_or_404(session, owner_id=owner_id, job_id=job_id)
    row.status = JOB_STATUS_FAILED
    row.completed_at = utc_now()
    baseline = row.started_at or row.requested_at
    row.duration_ms = max(int((_as_utc(row.completed_at) - _as_utc(baseline)).total_seconds() * 1000), 0)
    session.add(row)
    log_job_failed(session, publish_job_id=job_id, reason=reason)
    session.commit()
    session.refresh(row)
    return _detail(session, row)
