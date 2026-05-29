from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    OrganizationActivityEvent,
    OrganizationNotification,
    OrganizationNotificationReceipt,
)
from app.schemas.organization_activity import (
    ACTIVITY_CATEGORIES,
    LINEAGE_ACTIVITY_PREFIX,
    OrganizationActivityEventResponse,
    OrganizationActivityListResponse,
    OrganizationNotificationListResponse,
    OrganizationNotificationReceiptResponse,
    OrganizationNotificationResponse,
    OrganizationNotificationUnreadCountResponse,
)
from app.services.notification_permissions import (
    validate_activity_visibility,
    validate_notification_visibility,
    resolve_org_notification_access,
)

ENGINE_VERSION = "P42-07-v1"
ORG_VISIBILITY = "ORG"
SYSTEM_VISIBILITY = "SYSTEM"
NOTIFICATION_UNREAD = "UNREAD"
NOTIFICATION_READ = "READ"
NOTIFICATION_ACKNOWLEDGED = "ACKNOWLEDGED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(_json_safe(payload), sort_keys=True))


def _category_from_payload(payload: dict[str, Any]) -> str | None:
    category = payload.get("category")
    if isinstance(category, str) and category in ACTIVITY_CATEGORIES:
        return category
    return None


def _to_activity_response(row: OrganizationActivityEvent) -> OrganizationActivityEventResponse:
    assert row.id is not None
    payload = dict(row.activity_payload_json or {})
    return OrganizationActivityEventResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        actor_user_id=row.actor_user_id,
        activity_type=str(row.activity_type),
        activity_payload_json=payload,
        visibility_scope=str(row.visibility_scope),
        created_at=row.created_at,
        category=_category_from_payload(payload),
    )


def _receipt_for_notification(
    session: Session,
    *,
    notification_id: int,
    user_id: int,
) -> OrganizationNotificationReceipt | None:
    return session.exec(
        select(OrganizationNotificationReceipt)
        .where(OrganizationNotificationReceipt.organization_notification_id == notification_id)
        .where(OrganizationNotificationReceipt.user_id == user_id)
    ).first()


def _to_notification_response(
    session: Session,
    row: OrganizationNotification,
    *,
    viewer_user_id: int,
) -> OrganizationNotificationResponse:
    assert row.id is not None
    receipt = _receipt_for_notification(session, notification_id=int(row.id), user_id=viewer_user_id)
    return OrganizationNotificationResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        target_user_id=int(row.target_user_id),
        notification_type=str(row.notification_type),
        notification_title=str(row.notification_title),
        notification_body=str(row.notification_body),
        notification_status=str(row.notification_status),
        activity_event_id=row.activity_event_id,
        created_at=row.created_at,
        read_at=receipt.read_at if receipt else None,
        acknowledged_at=receipt.acknowledged_at if receipt else None,
    )


def append_lineage_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    lineage_type: str,
    payload: dict[str, Any] | None = None,
) -> OrganizationActivityEvent:
    row = OrganizationActivityEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"{LINEAGE_ACTIVITY_PREFIX}{lineage_type}",
        activity_payload_json=_stable_payload(payload or {}),
        visibility_scope=SYSTEM_VISIBILITY,
    )
    session.add(row)
    session.flush()
    return row


def create_activity_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    activity_type: str,
    activity_payload_json: dict[str, Any] | None = None,
    visibility_scope: str = ORG_VISIBILITY,
    category: str | None = None,
) -> OrganizationActivityEvent:
    payload = dict(activity_payload_json or {})
    if category is not None:
        payload["category"] = category
    payload["engine_version"] = ENGINE_VERSION
    row = OrganizationActivityEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=activity_type,
        activity_payload_json=_stable_payload(payload),
        visibility_scope=visibility_scope,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    append_lineage_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        lineage_type="activity_generated",
        payload={"activity_event_id": int(row.id), "activity_type": activity_type},
    )
    return row


def resolve_activity_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    activity_event: OrganizationActivityEvent,
) -> bool:
    from app.services.notification_permissions import resolve_activity_visibility as _resolve

    return _resolve(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_event=activity_event,
    )


def create_notification(
    session: Session,
    *,
    organization_id: int,
    target_user_id: int,
    notification_type: str,
    notification_title: str,
    notification_body: str,
    activity_event_id: int | None = None,
    actor_user_id: int | None = None,
) -> OrganizationNotification:
    row = OrganizationNotification(
        organization_id=organization_id,
        target_user_id=target_user_id,
        notification_type=notification_type,
        notification_title=notification_title,
        notification_body=notification_body,
        notification_status=NOTIFICATION_UNREAD,
        activity_event_id=activity_event_id,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    session.add(
        OrganizationNotificationReceipt(
            organization_notification_id=int(row.id),
            user_id=target_user_id,
        )
    )
    session.flush()
    append_lineage_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        lineage_type="notification_created",
        payload={"notification_id": int(row.id), "target_user_id": target_user_id},
    )
    return row


def list_org_activity_feed(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
) -> OrganizationActivityListResponse:
    validate_activity_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationActivityEvent)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .where(OrganizationActivityEvent.visibility_scope != SYSTEM_VISIBILITY)
        .where(~OrganizationActivityEvent.activity_type.like(f"{LINEAGE_ACTIVITY_PREFIX}%"))
        .order_by(OrganizationActivityEvent.created_at.desc(), OrganizationActivityEvent.id.desc())
    )
    rows = session.exec(stmt).all()
    if category:
        if category not in ACTIVITY_CATEGORIES:
            raise HTTPException(status_code=400, detail="Unsupported activity category.")
        rows = [row for row in rows if _category_from_payload(dict(row.activity_payload_json or {})) == category]
    total = len(rows)
    page = rows[offset : offset + limit]
    return OrganizationActivityListResponse(
        items=[_to_activity_response(row) for row in page],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_user_notifications(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> OrganizationNotificationListResponse:
    resolve_org_notification_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationNotification)
        .where(OrganizationNotification.organization_id == organization_id)
        .where(OrganizationNotification.target_user_id == actor_user_id)
        .order_by(OrganizationNotification.created_at.desc(), OrganizationNotification.id.desc())
    )
    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    total = session.exec(
        select(func.count())
        .select_from(OrganizationNotification)
        .where(OrganizationNotification.organization_id == organization_id)
        .where(OrganizationNotification.target_user_id == actor_user_id)
    ).one()
    return OrganizationNotificationListResponse(
        items=[_to_notification_response(session, row, viewer_user_id=actor_user_id) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def unread_notification_count(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> OrganizationNotificationUnreadCountResponse:
    resolve_org_notification_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total = session.exec(
        select(func.count())
        .select_from(OrganizationNotification)
        .where(OrganizationNotification.organization_id == organization_id)
        .where(OrganizationNotification.target_user_id == actor_user_id)
        .where(OrganizationNotification.notification_status == NOTIFICATION_UNREAD)
    ).one()
    return OrganizationNotificationUnreadCountResponse(unread_count=int(total))


def mark_notification_read(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    notification_id: int,
) -> OrganizationNotificationReceiptResponse:
    notification = validate_notification_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        notification_id=notification_id,
    )
    receipt = _receipt_for_notification(session, notification_id=int(notification.id or 0), user_id=actor_user_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Notification receipt not found.")
    if receipt.read_at is None:
        receipt.read_at = utc_now()
        session.add(receipt)
    if notification.notification_status == NOTIFICATION_UNREAD:
        notification.notification_status = NOTIFICATION_READ
        session.add(notification)
    session.flush()
    append_lineage_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        lineage_type="notification_read",
        payload={"notification_id": int(notification.id or 0)},
    )
    session.commit()
    session.refresh(notification)
    session.refresh(receipt)
    return OrganizationNotificationReceiptResponse(
        notification_id=int(notification.id or 0),
        notification_status=str(notification.notification_status),
        read_at=receipt.read_at,
        acknowledged_at=receipt.acknowledged_at,
    )


def acknowledge_notification(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    notification_id: int,
) -> OrganizationNotificationReceiptResponse:
    notification = validate_notification_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        notification_id=notification_id,
    )
    receipt = _receipt_for_notification(session, notification_id=int(notification.id or 0), user_id=actor_user_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Notification receipt not found.")
    now = utc_now()
    if receipt.read_at is None:
        receipt.read_at = now
    receipt.acknowledged_at = now
    notification.notification_status = NOTIFICATION_ACKNOWLEDGED
    session.add(receipt)
    session.add(notification)
    session.flush()
    append_lineage_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        lineage_type="notification_acknowledged",
        payload={"notification_id": int(notification.id or 0)},
    )
    from app.services.audit_ledger_integration import record_notification_audit

    record_notification_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="notification_acknowledged",
        resource_type="organization_notification",
        resource_id=int(notification.id or 0),
        payload={"notification_id": int(notification.id or 0), "activity_event_id": notification.activity_event_id},
    )
    session.commit()
    session.refresh(notification)
    session.refresh(receipt)
    return OrganizationNotificationReceiptResponse(
        notification_id=int(notification.id or 0),
        notification_status=str(notification.notification_status),
        read_at=receipt.read_at,
        acknowledged_at=receipt.acknowledged_at,
    )
