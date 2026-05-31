from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.data_integrity import AuditEvent, ChangeRecord
from app.schemas.data_integrity import (
    AuditEventDetail,
    AuditEventListResponse,
    AuditEventRead,
    ChangeRecordRead,
)


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _event_read(row: AuditEvent) -> AuditEventRead:
    return AuditEventRead.model_validate(row)


def _change_read(row: ChangeRecord) -> ChangeRecordRead:
    return ChangeRecordRead.model_validate(row)


def log_audit_event(
    session: Session,
    *,
    owner_user_id: int,
    actor_id: int | None,
    actor_type: str,
    action_type: str,
    entity_type: str,
    entity_id: int | None,
    source: str,
    event_payload_json: dict[str, Any] | None = None,
) -> AuditEventRead:
    row = AuditEvent(
        owner_user_id=owner_user_id,
        actor_id=actor_id,
        actor_type=actor_type.strip(),
        action_type=action_type.strip(),
        entity_type=entity_type.strip(),
        entity_id=entity_id,
        source=source.strip(),
        event_payload_json=_json_safe(event_payload_json or {}),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _event_read(row)


def log_change_record(
    session: Session,
    *,
    audit_event_id: int,
    field_name: str,
    before_value_json: Any = None,
    after_value_json: Any = None,
) -> ChangeRecordRead:
    row = ChangeRecord(
        audit_event_id=audit_event_id,
        field_name=field_name.strip(),
        before_value_json=_json_safe(before_value_json),
        after_value_json=_json_safe(after_value_json),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _change_read(row)


def list_audit_events(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> AuditEventListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(AuditEvent)
        .where(AuditEvent.owner_user_id == owner_user_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).all()
    items = [_event_read(row) for row in rows[offset : offset + limit]]
    return AuditEventListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def get_audit_event(session: Session, *, owner_user_id: int, audit_event_id: int) -> AuditEventDetail:
    row = session.get(AuditEvent, audit_event_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Audit event not found.")
    changes = session.exec(
        select(ChangeRecord)
        .where(ChangeRecord.audit_event_id == audit_event_id)
        .order_by(ChangeRecord.created_at.asc(), ChangeRecord.id.asc())
    ).all()
    return AuditEventDetail(event=_event_read(row), changes=[_change_read(change) for change in changes])
