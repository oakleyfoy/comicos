from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, select

from app.api.dependencies.security_context import require_non_revoked_session, require_valid_session
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Organization, User, UserAuthSession
from app.schemas.auth_sessions import (
    OrganizationSecurityContextRead,
    RevokeAuthSessionRequest,
    SwitchOrganizationRequest,
    UserAuthSessionListResponse,
    UserAuthSessionRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.security.security_context import resolve_user_security_context
from app.security.session_manager import revoke_all_user_sessions, revoke_session, switch_active_organization

auth_sessions_v1_router = APIRouter(prefix="/api/v1", tags=["Auth Sessions API v1 (P42)"])


def attach_auth_sessions_layer(app: FastAPI) -> None:
    app.include_router(auth_sessions_v1_router)


def _to_auth_session_read(row: UserAuthSession, *, current_session_id: int | None) -> UserAuthSessionRead:
    return UserAuthSessionRead(
        id=int(row.id or 0),
        user_id=row.user_id,
        device_label=row.device_label,
        device_type=row.device_type,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        organization_id=row.organization_id,
        session_status=row.session_status,
        issued_at=row.issued_at,
        last_seen_at=row.last_seen_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        is_current=current_session_id is not None and int(row.id or 0) == current_session_id,
    )


def _resolve_user_session_or_404(session: Session, *, session_id: int, user_id: int) -> UserAuthSession:
    row = session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.id == session_id)
        .where(UserAuthSession.user_id == user_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Authentication session not found.")
    return row


def _build_security_context_read(
    session: Session,
    *,
    current_user: User,
    auth_session: UserAuthSession,
) -> OrganizationSecurityContextRead:
    resolved = resolve_user_security_context(session, user=current_user, auth_session=auth_session)
    active_org = resolved.active_organization
    return OrganizationSecurityContextRead(
        id=int(resolved.security_context.id or 0),
        user_id=int(current_user.id or 0),
        active_organization_id=int(active_org.id or 0) if active_org is not None and active_org.id is not None else None,
        active_organization_slug=active_org.slug if active_org is not None else None,
        active_organization_display_name=active_org.display_name if active_org is not None else None,
        last_org_switch_at=resolved.security_context.last_org_switch_at,
        session_id=int(auth_session.id or 0),
        session_status=auth_session.session_status,
        session_expires_at=auth_session.expires_at,
        role_keys=list(resolved.role_keys),
        permission_keys=list(resolved.permission_keys),
    )


@auth_sessions_v1_router.get("/auth/sessions", response_model=ScanApiV1Envelope)
def v1_list_auth_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_valid_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.user_id == int(current_user.id))
        .order_by(UserAuthSession.issued_at.desc(), UserAuthSession.id.desc())
    ).all()
    items = [_to_auth_session_read(row, current_session_id=int(current_session.id or 0)) for row in rows]
    body = UserAuthSessionListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@auth_sessions_v1_router.get("/auth/security-context", response_model=ScanApiV1Envelope)
def v1_get_auth_security_context(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_non_revoked_session),
) -> ScanApiV1Envelope:
    body = _build_security_context_read(session, current_user=current_user, auth_session=current_session)
    return wrap_object(body, owner_user_id=current_user.id, snapshot_id=body.id)


@auth_sessions_v1_router.post("/auth/sessions/revoke", response_model=ScanApiV1Envelope)
def v1_revoke_auth_session(
    payload: RevokeAuthSessionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_non_revoked_session),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    target = _resolve_user_session_or_404(session, session_id=payload.session_id, user_id=int(current_user.id))
    body = _to_auth_session_read(
        revoke_session(session, auth_session=target, revoked_by_user_id=int(current_user.id), reason="user_requested"),
        current_session_id=int(current_session.id or 0),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@auth_sessions_v1_router.post("/auth/sessions/revoke-all", response_model=ScanApiV1Envelope)
def v1_revoke_all_auth_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_non_revoked_session),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = revoke_all_user_sessions(
        session,
        user_id=int(current_user.id),
        revoked_by_user_id=int(current_user.id),
        reason="user_requested_revoke_all",
    )
    items = [_to_auth_session_read(row, current_session_id=int(current_session.id or 0)) for row in rows]
    body = UserAuthSessionListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@auth_sessions_v1_router.post("/auth/security-context/switch-organization", response_model=ScanApiV1Envelope)
def v1_switch_active_organization(
    payload: SwitchOrganizationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    current_session: UserAuthSession = Depends(require_non_revoked_session),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    switch_active_organization(
        session,
        user_id=int(current_user.id),
        auth_session=current_session,
        organization_id=payload.organization_id,
    )
    session.refresh(current_session)
    body = _build_security_context_read(session, current_user=current_user, auth_session=current_session)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
