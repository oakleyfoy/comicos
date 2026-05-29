from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import (
    Organization,
    OrganizationMember,
    OrganizationMembershipRole,
    OrganizationRole,
    OrganizationSecurityContext,
    User,
    UserAuthSession,
)
from app.security.permissions import resolve_permission_keys, role_sort_key
from app.security.session_manager import append_session_event, ensure_security_context, utc_now


@dataclass(frozen=True)
class ResolvedUserSecurityContext:
    user: User
    auth_session: UserAuthSession
    security_context: OrganizationSecurityContext
    active_organization: Organization | None
    active_membership: OrganizationMember | None
    role_keys: tuple[str, ...]
    permission_keys: tuple[str, ...]
    invalid_reason: str | None = None


def _role_keys_for_member(session: Session, *, member_id: int) -> tuple[str, ...]:
    rows = session.exec(
        select(OrganizationMembershipRole, OrganizationRole)
        .join(OrganizationRole, OrganizationMembershipRole.organization_role_id == OrganizationRole.id)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .order_by(OrganizationMembershipRole.assigned_at.asc(), OrganizationMembershipRole.id.asc())
    ).all()
    ordered = sorted((role.role_key for _, role in rows), key=role_sort_key)
    return tuple(ordered)


def resolve_active_organization(session: Session, *, security_context: OrganizationSecurityContext) -> Organization | None:
    if security_context.active_organization_id is None:
        return None
    return session.get(Organization, security_context.active_organization_id)


def validate_active_membership(
    session: Session,
    *,
    user_id: int,
    organization_id: int,
) -> OrganizationMember:
    row = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.membership_status == "ACTIVE")
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active organization membership is required.")
    return row


def resolve_session_permissions(session: Session, *, member: OrganizationMember | None) -> tuple[str, ...]:
    if member is None or member.id is None:
        return tuple()
    role_keys = _role_keys_for_member(session, member_id=int(member.id))
    return resolve_permission_keys(role_keys)


def resolve_user_security_context(
    session: Session,
    *,
    user: User,
    auth_session: UserAuthSession,
) -> ResolvedUserSecurityContext:
    assert user.id is not None
    stored_context = ensure_security_context(session, user_id=int(user.id))
    active_organization = resolve_active_organization(session, security_context=stored_context)
    if active_organization is None:
        return ResolvedUserSecurityContext(
            user=user,
            auth_session=auth_session,
            security_context=stored_context,
            active_organization=None,
            active_membership=None,
            role_keys=tuple(),
            permission_keys=tuple(),
            invalid_reason=None,
        )

    membership = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == int(user.id))
        .where(OrganizationMember.organization_id == int(active_organization.id or 0))
        .where(OrganizationMember.membership_status == "ACTIVE")
    ).first()
    if membership is None:
        now = utc_now()
        stored_context.active_organization_id = None
        stored_context.updated_at = now
        auth_session.organization_id = None
        session.add(stored_context)
        session.add(auth_session)
        append_session_event(
            session,
            auth_session_id=int(auth_session.id or 0),
            user_id=int(user.id),
            organization_id=int(active_organization.id or 0),
            event_type="membership_validation_failed",
            event_payload_json={"reason": "active_membership_required"},
            created_at=now,
        )
        session.commit()
        session.refresh(stored_context)
        session.refresh(auth_session)
        return ResolvedUserSecurityContext(
            user=user,
            auth_session=auth_session,
            security_context=stored_context,
            active_organization=None,
            active_membership=None,
            role_keys=tuple(),
            permission_keys=tuple(),
            invalid_reason="active_membership_required",
        )

    role_keys = _role_keys_for_member(session, member_id=int(membership.id or 0))
    permission_keys = resolve_permission_keys(role_keys)
    return ResolvedUserSecurityContext(
        user=user,
        auth_session=auth_session,
        security_context=stored_context,
        active_organization=active_organization,
        active_membership=membership,
        role_keys=role_keys,
        permission_keys=permission_keys,
        invalid_reason=None,
    )


def validate_org_session_access(
    *,
    auth_session: UserAuthSession,
    requested_organization_id: int,
) -> None:
    if auth_session.organization_id is None:
        return
    if auth_session.organization_id != requested_organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session is bound to a different organization context.")
