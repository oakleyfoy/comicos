from __future__ import annotations

from sqlmodel import Session

from app.services.audit_ledger_service import create_audit_entry, create_compliance_event


def _record_category_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    audit_category: str,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
    compliance_event_type: str | None = None,
    severity_level: str | None = None,
) -> None:
    create_audit_entry(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category=audit_category,
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        audit_payload_json=payload,
    )
    if compliance_event_type is not None and severity_level is not None:
        create_compliance_event(
            session,
            organization_id=organization_id,
            compliance_event_type=compliance_event_type,
            severity_level=severity_level,
            event_payload_json=payload,
        )
    session.flush()


def record_organization_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
    compliance_event_type: str | None = None,
    severity_level: str | None = None,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="organization",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        compliance_event_type=compliance_event_type,
        severity_level=severity_level,
    )


def record_permissions_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="permissions",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )


def record_inventory_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="inventory",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )


def record_review_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="reviews",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )


def record_storefront_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="storefront",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )


def record_security_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
    compliance_event_type: str | None = None,
    severity_level: str | None = None,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="security",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        compliance_event_type=compliance_event_type,
        severity_level=severity_level,
    )


def record_session_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
    compliance_event_type: str | None = None,
    severity_level: str | None = None,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="sessions",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        compliance_event_type=compliance_event_type,
        severity_level=severity_level,
    )


def record_notification_audit(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None,
    payload: dict,
) -> None:
    _record_category_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category="notifications",
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
    )
