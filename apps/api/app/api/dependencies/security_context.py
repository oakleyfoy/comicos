from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.models import User, UserAuthSession
from app.security.security_context import ResolvedUserSecurityContext


def require_valid_session(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UserAuthSession:
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid authentication session is required.")
    return auth_session


def require_non_revoked_session(
    auth_session: UserAuthSession = Depends(require_valid_session),
) -> UserAuthSession:
    if auth_session.session_status != "ACTIVE" or auth_session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication session is invalid.")
    return auth_session


def require_active_org_context(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ResolvedUserSecurityContext:
    security_context = getattr(request.state, "security_context", None)
    if security_context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Security context is unavailable.")
    if security_context.active_organization is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active organization context is required.")
    return security_context


def require_valid_org_membership(
    security_context: ResolvedUserSecurityContext = Depends(require_active_org_context),
) -> ResolvedUserSecurityContext:
    if security_context.active_membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active organization membership is required.")
    return security_context
