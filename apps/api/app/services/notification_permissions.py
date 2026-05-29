from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import OrganizationActivityEvent, OrganizationMember, OrganizationNotification
from app.security.tenant_context import get_membership_record, get_organization_or_404
from app.services.authorization_service import evaluate_permission, validate_org_access

ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"
FEED_VIEW_PERMISSION = "operations:view"
SYSTEM_VISIBILITY = "SYSTEM"
LINEAGE_PREFIX = "lineage."


@dataclass(frozen=True)
class ActivityFeedAccess:
    can_view_feed: bool
    can_view_notifications: bool
    reason: str


def _record_unauthorized_feed_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    reason: str,
    action_key: str,
) -> None:
    from app.services.activity_feed_service import append_lineage_activity

    audit_session = Session(session.get_bind())
    try:
        append_lineage_activity(
            audit_session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            lineage_type="unauthorized_feed_access_attempt",
            payload={"reason": reason, "action_key": action_key},
        )
        audit_session.commit()
    finally:
        audit_session.close()


def resolve_org_notification_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> None:
    member = get_membership_record(
        session,
        organization_id=organization_id,
        user_id=actor_user_id,
        active_only=True,
    )
    if member is None:
        _record_unauthorized_feed_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason="membership_required",
            action_key="notifications:view",
        )
        raise HTTPException(status_code=403, detail="Organization membership is required.")


def validate_activity_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> None:
    organization = get_organization_or_404(session, organization_id=organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise HTTPException(status_code=409, detail="Organization is not active.")
    resolve_org_notification_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=FEED_VIEW_PERMISSION,
    )
    if not evaluation.allowed:
        _record_unauthorized_feed_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason=evaluation.reason,
            action_key=FEED_VIEW_PERMISSION,
        )
        raise HTTPException(status_code=403, detail="Organization activity feed access denied.")


def validate_notification_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    notification_id: int,
) -> OrganizationNotification:
    resolve_org_notification_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    notification = session.get(OrganizationNotification, notification_id)
    if notification is None or int(notification.organization_id) != organization_id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if int(notification.target_user_id) != actor_user_id:
        _record_unauthorized_feed_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason="notification_target_mismatch",
            action_key="notifications:view",
        )
        raise HTTPException(status_code=403, detail="Notification access denied.")
    return notification


def resolve_user_activity_feed(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> tuple[int, ...]:
    validate_activity_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    validate_org_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    rows = session.exec(
        select(OrganizationActivityEvent.id)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .where(OrganizationActivityEvent.visibility_scope != SYSTEM_VISIBILITY)
        .where(OrganizationActivityEvent.activity_type.not_like(f"{LINEAGE_PREFIX}%"))
        .order_by(OrganizationActivityEvent.created_at.desc(), OrganizationActivityEvent.id.desc())
    ).all()
    return tuple(int(row) for row in rows if row is not None)


def resolve_activity_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    activity_event: OrganizationActivityEvent,
) -> bool:
    if activity_event.visibility_scope == SYSTEM_VISIBILITY:
        return False
    if activity_event.activity_type.startswith(LINEAGE_PREFIX):
        return False
    try:
        validate_activity_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    except HTTPException:
        append_denied = Session(session.get_bind())
        try:
            from app.services.activity_feed_service import append_lineage_activity

            append_lineage_activity(
                append_denied,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                lineage_type="visibility_denied",
                payload={"activity_event_id": int(activity_event.id or 0)},
            )
            append_denied.commit()
        finally:
            append_denied.close()
        return False
    return True
