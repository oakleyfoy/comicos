from __future__ import annotations

from sqlmodel import Session

from app.services.activity_feed_service import create_activity_event, create_notification


def record_organization_membership_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_kind: str,
    payload: dict,
    notify_user_id: int | None = None,
) -> None:
    activity = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"organization.{event_kind}",
        activity_payload_json=payload,
        category="organization",
    )
    if notify_user_id is not None:
        create_notification(
            session,
            organization_id=organization_id,
            target_user_id=notify_user_id,
            notification_type=f"organization.{event_kind}",
            notification_title=payload.get("title", "Organization update"),
            notification_body=payload.get("body", "Organization membership changed."),
            activity_event_id=int(activity.id or 0),
            actor_user_id=actor_user_id,
        )
    session.flush()


def record_inventory_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_kind: str,
    payload: dict,
    notify_user_id: int | None = None,
) -> None:
    activity = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"inventory.{event_kind}",
        activity_payload_json=payload,
        category="inventory",
    )
    if notify_user_id is not None:
        create_notification(
            session,
            organization_id=organization_id,
            target_user_id=notify_user_id,
            notification_type=f"inventory.{event_kind}",
            notification_title=payload.get("title", "Inventory workflow update"),
            notification_body=payload.get("body", "An inventory workflow event occurred."),
            activity_event_id=int(activity.id or 0),
            actor_user_id=actor_user_id,
        )
    session.flush()


def record_review_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_kind: str,
    payload: dict,
    notify_user_id: int | None = None,
) -> None:
    activity = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"reviews.{event_kind}",
        activity_payload_json=payload,
        category="reviews",
    )
    if notify_user_id is not None:
        create_notification(
            session,
            organization_id=organization_id,
            target_user_id=notify_user_id,
            notification_type=f"reviews.{event_kind}",
            notification_title=payload.get("title", "Review update"),
            notification_body=payload.get("body", "A review workflow event occurred."),
            activity_event_id=int(activity.id or 0),
            actor_user_id=actor_user_id,
        )
    session.flush()


def record_storefront_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_kind: str,
    payload: dict,
) -> None:
    create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"storefront.{event_kind}",
        activity_payload_json=payload,
        category="storefront",
    )
    session.flush()


def record_permissions_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_kind: str,
    payload: dict,
    notify_user_id: int | None = None,
) -> None:
    activity = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"permissions.{event_kind}",
        activity_payload_json=payload,
        category="permissions",
    )
    if notify_user_id is not None:
        create_notification(
            session,
            organization_id=organization_id,
            target_user_id=notify_user_id,
            notification_type=f"permissions.{event_kind}",
            notification_title=payload.get("title", "Permission update"),
            notification_body=payload.get("body", "Your organization permissions changed."),
            activity_event_id=int(activity.id or 0),
            actor_user_id=actor_user_id,
        )
    session.flush()


def record_security_activity(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_kind: str,
    payload: dict,
    notify_user_id: int | None = None,
) -> None:
    activity = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        activity_type=f"security.{event_kind}",
        activity_payload_json=payload,
        category="security",
    )
    if notify_user_id is not None:
        create_notification(
            session,
            organization_id=organization_id,
            target_user_id=notify_user_id,
            notification_type=f"security.{event_kind}",
            notification_title=payload.get("title", "Security update"),
            notification_body=payload.get("body", "A security event occurred in your organization."),
            activity_event_id=int(activity.id or 0),
            actor_user_id=actor_user_id,
        )
    session.flush()
