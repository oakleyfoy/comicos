from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.models import MarketplaceAccount, MarketplaceConnectionEvent, Organization
from app.security.permissions import resolve_permission_keys
from app.services.authorization_service import resolve_user_organization_roles


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class MarketplacePermissionResolution:
    organization_id: int
    actor_user_id: int
    can_view: bool
    can_manage: bool
    role_keys: tuple[str, ...]
    permission_keys: tuple[str, ...]
    reason: str


def _organization_or_404(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


def _record_unauthorized_attempt(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
    actor_user_id: int | None,
    action: str,
    reason: str,
    extra_payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        MarketplaceConnectionEvent(
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_access_attempt",
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


def resolve_marketplace_permissions(
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


def validate_org_marketplace_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            marketplace_account_id=None,
            actor_user_id=actor_user_id,
            action="marketplace:view",
            reason=resolution.reason,
        )
        raise HTTPException(status_code=403, detail="Marketplace visibility is denied for this organization.")
    return resolution


def validate_marketplace_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account: MarketplaceAccount | None = None,
    requested_account_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = validate_org_marketplace_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if marketplace_account is not None and marketplace_account.organization_id != organization_id:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            marketplace_account_id=requested_account_id or int(marketplace_account.id or 0) or None,
            actor_user_id=actor_user_id,
            action="marketplace:view",
            reason="cross_organization_account_access_denied",
        )
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return resolution


def validate_marketplace_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account: MarketplaceAccount | None = None,
    requested_account_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if marketplace_account is not None and marketplace_account.organization_id != organization_id:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            marketplace_account_id=requested_account_id or int(marketplace_account.id or 0) or None,
            actor_user_id=actor_user_id,
            action="marketplace:manage",
            reason="cross_organization_account_access_denied",
        )
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    if not resolution.can_manage:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            marketplace_account_id=requested_account_id,
            actor_user_id=actor_user_id,
            action="marketplace:manage",
            reason="permission_missing" if resolution.can_view else resolution.reason,
        )
        raise HTTPException(status_code=403, detail="Marketplace management is denied for this organization.")
    return resolution
