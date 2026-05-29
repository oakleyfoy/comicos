from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.models import MobileFoundationEvent, Organization
from app.security.permissions import resolve_permission_keys
from app.services.authorization_service import resolve_user_organization_roles
from app.services.marketplace_permissions import MarketplacePermissionResolution, utc_now, _json_safe


def _organization_or_404(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


def _record_unauthorized_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    action: str,
    reason: str,
    extra_payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        MobileFoundationEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_access_attempt",
            event_payload_json=_json_safe(
                {
                    "action": action,
                    "reason": reason,
                    **(extra_payload or {}),
                }
            ),
            created_at=utc_now(),
        )
    )
    session.commit()


def resolve_mobile_permissions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplacePermissionResolution:
    _organization_or_404(session, organization_id)
    role_assignments = resolve_user_organization_roles(session, organization_id=organization_id, user_id=actor_user_id)
    role_keys = tuple(row.role_key for row in role_assignments)
    permission_keys = resolve_permission_keys(role_keys)
    can_manage = "organization:update" in permission_keys
    can_view = "organization:view" in permission_keys or can_manage
    reason = "permission_granted" if can_view else ("permission_missing" if role_keys else "membership_required")
    return MarketplacePermissionResolution(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        can_view=can_view,
        can_manage=can_manage,
        role_keys=role_keys,
        permission_keys=permission_keys,
        reason=reason,
    )


def validate_mobile_view_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplacePermissionResolution:
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="mobile:view",
            reason=resolution.reason,
        )
        raise HTTPException(status_code=403, detail="Mobile visibility is denied for this organization.")
    return resolution


def validate_mobile_manage_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplacePermissionResolution:
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="mobile:manage",
            reason=resolution.reason,
        )
        raise HTTPException(status_code=403, detail="Mobile management is denied for this organization.")
    return resolution
