from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    Organization,
    OrganizationEvent,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationMembershipRole,
    OrganizationRole,
    User,
)
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationArchiveRequest,
    OrganizationEventListResponse,
    OrganizationEventResponse,
    OrganizationInvitationResponse,
    OrganizationInviteRequest,
    OrganizationListResponse,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
)
from app.security.permissions import ensure_system_roles, resolve_permission_keys, role_sort_key

ENGINE_VERSION = "P42-01-v1"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"
ARCHIVED_ORGANIZATION_STATUS = "ARCHIVED"
ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
REMOVED_MEMBERSHIP_STATUS = "REMOVED"
PENDING_INVITATION_STATUS = "PENDING"
ACCEPTED_INVITATION_STATUS = "ACCEPTED"
EXPIRED_INVITATION_STATUS = "EXPIRED"
_ALLOWED_ORGANIZATION_TYPES = {"DEALER", "COLLECTOR", "INTERNAL"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="Organization slug must contain at least two letters or numbers.")
    return normalized[:120]


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _public_id(*, owner_user_id: int, slug: str) -> str:
    return f"org_{_stable_hash({'owner_user_id': owner_user_id, 'slug': slug})[:20]}"


def _invitation_token(*, organization: Organization, email: str, invited_by_user_id: int, sequence: int) -> str:
    payload = {
        "organization_public_id": organization.public_id,
        "email": email,
        "invited_by_user_id": invited_by_user_id,
        "sequence": sequence,
        "engine_version": ENGINE_VERSION,
    }
    return _stable_hash(payload)


def _organization_or_404(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


def _member_for_user(session: Session, *, organization_id: int, user_id: int) -> OrganizationMember | None:
    return session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user_id)
    ).first()


def _require_org_access(session: Session, *, organization_id: int, user_id: int, require_owner: bool = False) -> Organization:
    organization = _organization_or_404(session, organization_id)
    if organization.owner_user_id == user_id:
        return organization
    if require_owner:
        raise HTTPException(status_code=404, detail="Organization not found.")
    member = _member_for_user(session, organization_id=organization_id, user_id=user_id)
    if member is None or member.membership_status != ACTIVE_MEMBERSHIP_STATUS:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


def _organization_counts(session: Session, *, organization_id: int) -> tuple[int, int]:
    active_members = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
        .order_by(OrganizationMember.id)
    ).all()
    pending_invitations = session.exec(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == organization_id)
        .where(OrganizationInvitation.status == PENDING_INVITATION_STATUS)
        .order_by(OrganizationInvitation.id)
    ).all()
    return len(active_members), len(pending_invitations)


def _member_role_keys(session: Session, *, member_id: int) -> list[str]:
    rows = session.exec(
        select(OrganizationMembershipRole, OrganizationRole)
        .join(OrganizationRole, OrganizationMembershipRole.organization_role_id == OrganizationRole.id)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .order_by(OrganizationMembershipRole.assigned_at.asc(), OrganizationMembershipRole.id.asc())
    ).all()
    role_keys = [role.role_key for _, role in rows]
    return sorted(role_keys, key=role_sort_key)


def _member_permission_keys(session: Session, *, member_id: int) -> list[str]:
    return list(resolve_permission_keys(tuple(_member_role_keys(session, member_id=member_id))))


def _ensure_member_role_assignment(
    session: Session,
    *,
    organization_id: int,
    member_id: int,
    role_key: str,
    assigned_by_user_id: int,
    assigned_at: datetime,
) -> None:
    roles = ensure_system_roles(session, organization_id=organization_id, created_at=assigned_at)
    role = next((row for row in roles if row.role_key == role_key), None)
    if role is None or role.id is None:
        raise RuntimeError("Organization role initialization failed.")
    existing = session.exec(
        select(OrganizationMembershipRole)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .where(OrganizationMembershipRole.organization_role_id == int(role.id))
    ).first()
    if existing is None:
        session.add(
            OrganizationMembershipRole(
                organization_member_id=member_id,
                organization_role_id=int(role.id),
                assigned_by_user_id=assigned_by_user_id,
                assigned_at=assigned_at,
            )
        )


def _record_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> None:
    session.add(
        OrganizationEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_payload_json=_json_safe(event_payload_json),
        )
    )


def _to_organization_response(session: Session, row: Organization, *, current_user_id: int | None = None) -> OrganizationResponse:
    active_member_count, pending_invitation_count = _organization_counts(session, organization_id=int(row.id or 0))
    current_user_role_keys: list[str] = []
    current_user_permission_keys: list[str] = []
    if current_user_id is not None:
        member = _member_for_user(session, organization_id=int(row.id or 0), user_id=current_user_id)
        if member is not None and member.id is not None and member.membership_status == ACTIVE_MEMBERSHIP_STATUS:
            current_user_role_keys = _member_role_keys(session, member_id=int(member.id))
            current_user_permission_keys = list(resolve_permission_keys(tuple(current_user_role_keys)))
    return OrganizationResponse(
        id=int(row.id or 0),
        public_id=row.public_id,
        owner_user_id=row.owner_user_id,
        display_name=row.display_name,
        slug=row.slug,
        organization_type=row.organization_type,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
        active_member_count=active_member_count,
        pending_invitation_count=pending_invitation_count,
        current_user_role_keys=current_user_role_keys,
        current_user_permission_keys=current_user_permission_keys,
    )


def _to_member_response(session: Session, row: OrganizationMember) -> OrganizationMemberResponse:
    user = session.get(User, row.user_id)
    organization = session.get(Organization, row.organization_id)
    role_keys = _member_role_keys(session, member_id=int(row.id or 0)) if row.id is not None else []
    return OrganizationMemberResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        user_id=row.user_id,
        user_email=user.email if user is not None else "",
        membership_status=row.membership_status,
        joined_at=row.joined_at,
        invited_by_user_id=row.invited_by_user_id,
        removed_at=row.removed_at,
        is_owner=organization is not None and organization.owner_user_id == row.user_id,
        role_keys=role_keys,
        effective_permission_keys=list(resolve_permission_keys(tuple(role_keys))),
    )


def _to_invitation_response(row: OrganizationInvitation) -> OrganizationInvitationResponse:
    return OrganizationInvitationResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        email=row.email,
        invitation_token=row.invitation_token,
        status=row.status,
        expires_at=row.expires_at,
        accepted_at=row.accepted_at,
        invited_by_user_id=row.invited_by_user_id,
        created_at=row.created_at,
    )


def _to_event_response(row: OrganizationEvent) -> OrganizationEventResponse:
    return OrganizationEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(sorted((row.event_payload_json or {}).items())),
        created_at=row.created_at,
    )


def create_organization(session: Session, *, owner_user_id: int, payload: OrganizationCreateRequest) -> OrganizationResponse:
    slug = _slugify(payload.slug or payload.display_name)
    organization_type = payload.organization_type.strip().upper()
    if organization_type not in _ALLOWED_ORGANIZATION_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported organization type.")
    existing = session.exec(select(Organization).where(Organization.slug == slug)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Organization slug is already in use.")

    organization = Organization(
        public_id=_public_id(owner_user_id=owner_user_id, slug=slug),
        owner_user_id=owner_user_id,
        display_name=payload.display_name.strip(),
        slug=slug,
        organization_type=organization_type,
        status=ACTIVE_ORGANIZATION_STATUS,
    )
    session.add(organization)
    session.flush()
    assert organization.id is not None

    owner_member = OrganizationMember(
        organization_id=int(organization.id),
        user_id=owner_user_id,
        membership_status=ACTIVE_MEMBERSHIP_STATUS,
        invited_by_user_id=owner_user_id,
    )
    session.add(owner_member)
    session.flush()
    _ensure_member_role_assignment(
        session,
        organization_id=int(organization.id),
        member_id=int(owner_member.id),
        role_key="owner",
        assigned_by_user_id=owner_user_id,
        assigned_at=organization.created_at,
    )
    _record_event(
        session,
        organization_id=int(organization.id),
        actor_user_id=owner_user_id,
        event_type="organization_created",
        event_payload_json={
            "display_name": organization.display_name,
            "organization_type": organization.organization_type,
            "owner_user_id": owner_user_id,
            "public_id": organization.public_id,
            "slug": organization.slug,
        },
    )
    session.commit()
    session.refresh(organization)
    return _to_organization_response(session, organization, current_user_id=owner_user_id)


def archive_organization(
    session: Session,
    *,
    owner_user_id: int,
    organization_id: int,
    payload: OrganizationArchiveRequest,
) -> OrganizationResponse:
    organization = _require_org_access(session, organization_id=organization_id, user_id=owner_user_id, require_owner=True)
    if organization.status == ARCHIVED_ORGANIZATION_STATUS:
        return _to_organization_response(session, organization, current_user_id=owner_user_id)

    now = utc_now()
    organization.status = ARCHIVED_ORGANIZATION_STATUS
    organization.archived_at = now
    organization.updated_at = now
    session.add(organization)
    _record_event(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        event_type="organization_archived",
        event_payload_json={"reason": payload.reason or "", "status": organization.status},
    )
    session.commit()
    session.refresh(organization)
    return _to_organization_response(session, organization, current_user_id=owner_user_id)


def invite_member(
    session: Session,
    *,
    owner_user_id: int,
    organization_id: int,
    payload: OrganizationInviteRequest,
) -> tuple[OrganizationInvitationResponse, bool]:
    organization = _require_org_access(session, organization_id=organization_id, user_id=owner_user_id, require_owner=True)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise HTTPException(status_code=409, detail="Archived organizations do not accept invitations.")

    email = _normalize_email(payload.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is not None:
        member = _member_for_user(session, organization_id=organization_id, user_id=int(user.id or 0))
        if member is not None and member.membership_status == ACTIVE_MEMBERSHIP_STATUS:
            raise HTTPException(status_code=409, detail="User is already an active organization member.")

    pending = session.exec(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == organization_id)
        .where(OrganizationInvitation.email == email)
        .where(OrganizationInvitation.status == PENDING_INVITATION_STATUS)
        .order_by(OrganizationInvitation.created_at.desc(), OrganizationInvitation.id.desc())
    ).first()
    if pending is not None and _coerce_utc(pending.expires_at) >= utc_now():
        return _to_invitation_response(pending), False
    if pending is not None and _coerce_utc(pending.expires_at) < utc_now():
        pending.status = EXPIRED_INVITATION_STATUS
        session.add(pending)
        session.flush()

    existing_count = len(
        session.exec(
            select(OrganizationInvitation)
            .where(OrganizationInvitation.organization_id == organization_id)
            .where(OrganizationInvitation.email == email)
            .order_by(OrganizationInvitation.id)
        ).all()
    )
    invitation = OrganizationInvitation(
        organization_id=organization_id,
        email=email,
        invitation_token=_invitation_token(
            organization=organization,
            email=email,
            invited_by_user_id=owner_user_id,
            sequence=existing_count + 1,
        ),
        status=PENDING_INVITATION_STATUS,
        expires_at=utc_now() + timedelta(days=payload.expires_in_days),
        invited_by_user_id=owner_user_id,
    )
    session.add(invitation)
    session.flush()
    _record_event(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        event_type="member_invited",
        event_payload_json={
            "email": email,
            "expires_at": invitation.expires_at,
            "invitation_id": int(invitation.id or 0),
            "invitation_token": invitation.invitation_token,
        },
    )
    session.commit()
    session.refresh(invitation)
    return _to_invitation_response(invitation), True


def accept_invitation(session: Session, *, current_user: User, token: str) -> OrganizationMemberResponse:
    invitation = session.exec(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.invitation_token == token.strip())
    ).first()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invitation.status != PENDING_INVITATION_STATUS:
        raise HTTPException(status_code=409, detail="Invitation is no longer pending.")
    if _coerce_utc(invitation.expires_at) < utc_now():
        invitation.status = EXPIRED_INVITATION_STATUS
        session.add(invitation)
        session.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired.")
    if _normalize_email(current_user.email) != invitation.email:
        raise HTTPException(status_code=403, detail="Invitation email does not match the current user.")

    organization = _organization_or_404(session, invitation.organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise HTTPException(status_code=409, detail="Archived organizations do not accept invitations.")

    assert current_user.id is not None
    existing_member = _member_for_user(session, organization_id=organization.id or 0, user_id=int(current_user.id))
    if existing_member is not None:
        if existing_member.membership_status == ACTIVE_MEMBERSHIP_STATUS:
            if existing_member.id is not None and existing_member.user_id != organization.owner_user_id:
                _ensure_member_role_assignment(
                    session,
                    organization_id=int(organization.id or 0),
                    member_id=int(existing_member.id),
                    role_key="viewer",
                    assigned_by_user_id=invitation.invited_by_user_id,
                    assigned_at=existing_member.joined_at,
                )
            invitation.status = ACCEPTED_INVITATION_STATUS
            invitation.accepted_at = existing_member.joined_at
            session.add(invitation)
            session.commit()
            session.refresh(existing_member)
            return _to_member_response(session, existing_member)
        raise HTTPException(status_code=409, detail="Historical membership already exists for this user.")

    member = OrganizationMember(
        organization_id=int(organization.id or 0),
        user_id=int(current_user.id),
        membership_status=ACTIVE_MEMBERSHIP_STATUS,
        joined_at=utc_now(),
        invited_by_user_id=invitation.invited_by_user_id,
    )
    session.add(member)
    session.flush()
    if member.id is None:
        raise RuntimeError("Organization membership creation failed.")
    _ensure_member_role_assignment(
        session,
        organization_id=int(organization.id or 0),
        member_id=int(member.id),
        role_key="viewer",
        assigned_by_user_id=invitation.invited_by_user_id,
        assigned_at=member.joined_at,
    )
    invitation.status = ACCEPTED_INVITATION_STATUS
    invitation.accepted_at = member.joined_at
    session.add(invitation)
    _record_event(
        session,
        organization_id=int(organization.id or 0),
        actor_user_id=int(current_user.id),
        event_type="invitation_accepted",
        event_payload_json={
            "email": invitation.email,
            "invitation_id": int(invitation.id or 0),
            "member_user_id": int(current_user.id),
        },
    )
    from app.services.activity_feed_integration import record_organization_membership_activity

    record_organization_membership_activity(
        session,
        organization_id=int(organization.id or 0),
        actor_user_id=int(current_user.id),
        event_kind="invitation_accepted",
        payload={
            "title": "Invitation accepted",
            "body": f"{invitation.email} joined the organization.",
            "member_user_id": int(current_user.id),
            "invitation_id": int(invitation.id or 0),
        },
    )
    from app.services.audit_ledger_integration import record_organization_audit

    record_organization_audit(
        session,
        organization_id=int(organization.id or 0),
        actor_user_id=int(current_user.id),
        audit_action="invitation_accepted",
        resource_type="organization_member",
        resource_id=int(current_user.id),
        payload={
            "invitation_id": int(invitation.id or 0),
            "member_user_id": int(current_user.id),
            "email": invitation.email,
        },
    )
    session.commit()
    session.refresh(member)
    return _to_member_response(session, member)


def remove_member(
    session: Session,
    *,
    owner_user_id: int,
    organization_id: int,
    member_user_id: int,
) -> OrganizationMemberResponse:
    organization = _require_org_access(session, organization_id=organization_id, user_id=owner_user_id, require_owner=True)
    if organization.owner_user_id == member_user_id:
        raise HTTPException(status_code=409, detail="Organization owners cannot be removed in this phase.")

    member = _member_for_user(session, organization_id=organization_id, user_id=member_user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Organization member not found.")
    if member.membership_status == REMOVED_MEMBERSHIP_STATUS:
        return _to_member_response(session, member)

    member.membership_status = REMOVED_MEMBERSHIP_STATUS
    member.removed_at = utc_now()
    session.add(member)
    _record_event(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        event_type="member_removed",
        event_payload_json={"member_user_id": member_user_id, "removed_at": member.removed_at},
    )
    from app.services.activity_feed_integration import record_organization_membership_activity

    record_organization_membership_activity(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        event_kind="member_removed",
        payload={
            "title": "Member removed",
            "body": f"Member user {member_user_id} was removed from the organization.",
            "member_user_id": member_user_id,
        },
    )
    from app.services.audit_ledger_integration import record_organization_audit

    record_organization_audit(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        audit_action="member_removed",
        resource_type="organization_member",
        resource_id=member_user_id,
        payload={
            "member_user_id": member_user_id,
            "removed_at": member.removed_at,
        },
        compliance_event_type="organization.member_removed",
        severity_level="critical",
    )
    session.commit()
    session.refresh(member)
    return _to_member_response(session, member)


def list_organizations(session: Session, *, user_id: int, limit: int, offset: int) -> OrganizationListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    member_rows = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
        .order_by(OrganizationMember.organization_id)
    ).all()
    organization_ids = {row.organization_id for row in member_rows}
    owned_rows = session.exec(
        select(Organization).where(Organization.owner_user_id == user_id).order_by(Organization.id)
    ).all()
    organization_ids.update(int(row.id or 0) for row in owned_rows if row.id is not None)
    ordered = [
        _to_organization_response(session, row, current_user_id=user_id)
        for row in session.exec(
            select(Organization)
            .where(Organization.id.in_(organization_ids) if organization_ids else False)
            .order_by(Organization.status.asc(), Organization.display_name.asc(), Organization.id.asc())
        ).all()
    ] if organization_ids else []
    sliced = ordered[offset : offset + limit]
    return OrganizationListResponse(items=sliced, total_items=len(ordered), limit=limit, offset=offset)


def get_organization(session: Session, *, user_id: int, organization_id: int) -> OrganizationResponse:
    organization = _require_org_access(session, organization_id=organization_id, user_id=user_id)
    return _to_organization_response(session, organization, current_user_id=user_id)


def list_organization_members(
    session: Session,
    *,
    user_id: int,
    organization_id: int,
    limit: int,
    offset: int,
) -> OrganizationMemberListResponse:
    _require_org_access(session, organization_id=organization_id, user_id=user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.joined_at.asc(), OrganizationMember.id.asc())
    ).all()
    items = [_to_member_response(session, row) for row in rows]
    return OrganizationMemberListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def list_organization_events(
    session: Session,
    *,
    user_id: int,
    organization_id: int,
    limit: int,
    offset: int,
) -> OrganizationEventListResponse:
    _require_org_access(session, organization_id=organization_id, user_id=user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(OrganizationEvent)
        .where(OrganizationEvent.organization_id == organization_id)
        .order_by(OrganizationEvent.created_at.asc(), OrganizationEvent.id.asc())
    ).all()
    items = [_to_event_response(row) for row in rows]
    return OrganizationEventListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)
