"""P72-02 grading lifecycle audit log (append-only)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.p72_grading_operations import P72GradingAuditLog
from app.schemas.p72_grading_operations import P72GradingAuditLogRead


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def append_grading_audit_log(
    session: Session,
    *,
    owner_user_id: int,
    queue_entry_id: int,
    event_type: str,
    prior_status: str | None,
    new_status: str | None,
    created_by_user_id: int | None = None,
    metadata_json: dict | None = None,
) -> P72GradingAuditLog:
    row = P72GradingAuditLog(
        owner_user_id=owner_user_id,
        queue_entry_id=queue_entry_id,
        event_type=event_type,
        prior_status=prior_status,
        new_status=new_status,
        metadata_json=dict(metadata_json or {}),
        created_by_user_id=created_by_user_id,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def list_audit_for_queue_entry(
    session: Session,
    *,
    owner_user_id: int,
    queue_entry_id: int,
    limit: int = 50,
) -> list[P72GradingAuditLogRead]:
    rows = session.exec(
        select(P72GradingAuditLog)
        .where(P72GradingAuditLog.owner_user_id == owner_user_id)
        .where(P72GradingAuditLog.queue_entry_id == queue_entry_id)
        .order_by(P72GradingAuditLog.created_at.desc(), P72GradingAuditLog.id.desc())
        .limit(min(max(limit, 1), 200))
    ).all()
    return [P72GradingAuditLogRead.model_validate(r) for r in rows]
