from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlmodel import Session

from app.api.dependencies.security_context import require_non_revoked_session
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User, UserAuthSession
from app.security.security_context import validate_org_session_access
from app.security.tenant_context import OrganizationActorContext, resolve_organization_context
from app.services.authorization_service import (
    resolve_user_organization_roles,
    validate_org_access,
    validate_org_permission,
)


def resolve_org_context(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_non_revoked_session),
) -> OrganizationActorContext:
    assert current_user.id is not None
    validate_org_session_access(auth_session=current_session, requested_organization_id=organization_id)
    return resolve_organization_context(session, organization_id=organization_id, actor_user_id=int(current_user.id))


def require_org_membership(
    context: OrganizationActorContext = Depends(resolve_org_context),
    session: Session = Depends(get_session),
) -> OrganizationActorContext:
    validate_org_access(session, organization_id=int(context.organization.id or 0), actor_user_id=context.actor_user_id)
    return resolve_organization_context(session, organization_id=int(context.organization.id or 0), actor_user_id=context.actor_user_id)


def require_org_role(role_key: str):
    def dependency(
        context: OrganizationActorContext = Depends(require_org_membership),
        session: Session = Depends(get_session),
    ) -> OrganizationActorContext:
        assignments = resolve_user_organization_roles(
            session,
            organization_id=int(context.organization.id or 0),
            user_id=context.actor_user_id,
        )
        if role_key not in {row.role_key for row in assignments}:
            raise HTTPException(status_code=403, detail=f"Missing required organization role: {role_key}")
        return context

    return dependency


def require_org_permission(permission_key: str):
    def dependency(
        context: OrganizationActorContext = Depends(resolve_org_context),
        session: Session = Depends(get_session),
    ) -> OrganizationActorContext:
        validate_org_permission(
            session,
            organization_id=int(context.organization.id or 0),
            actor_user_id=context.actor_user_id,
            action_key=permission_key,
        )
        return resolve_organization_context(session, organization_id=int(context.organization.id or 0), actor_user_id=context.actor_user_id)

    return dependency
