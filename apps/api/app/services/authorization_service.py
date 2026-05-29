from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    Organization,
    OrganizationMember,
    OrganizationMembershipRole,
    OrganizationPermissionAudit,
    OrganizationRole,
)
from app.schemas.organization import (
    OrganizationMembershipRoleListResponse,
    OrganizationMembershipRoleResponse,
    OrganizationPermissionAuditListResponse,
    OrganizationPermissionAuditResponse,
    OrganizationRoleListResponse,
    OrganizationRoleResponse,
)
from app.security.permissions import (
    ROLE_DEFINITION_BY_KEY,
    ensure_system_roles,
    resolve_permission_keys,
    role_sort_key,
)
from app.security.tenant_context import (
    OrganizationActorContext,
    constrain_query_to_organization,
    get_membership_record,
    get_organization_or_404,
    require_active_membership,
    resolve_organization_context,
)

ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
DENIED_RESULT = "DENIED"
GRANTED_RESULT = "GRANTED"
ASSIGNED_RESULT = "ASSIGNED"
REMOVED_RESULT = "REMOVED"


@dataclass(frozen=True)
class PermissionEvaluation:
    organization_id: int
    actor_user_id: int
    action_key: str
    target_user_id: int | None
    allowed: bool
    role_keys: tuple[str, ...]
    permission_keys: tuple[str, ...]
    reason: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _audit_permission(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    target_user_id: int | None,
    action_key: str,
    permission_result: str,
    evaluation_context_json: dict[str, Any],
) -> None:
    session.add(
        OrganizationPermissionAudit(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action_key=action_key,
            permission_result=permission_result,
            evaluation_context_json=_json_safe(evaluation_context_json),
        )
    )


def _active_member_or_none(session: Session, *, organization_id: int, user_id: int) -> OrganizationMember | None:
    return get_membership_record(session, organization_id=organization_id, user_id=user_id, active_only=True)


def _member_in_organization_or_404(session: Session, *, organization_id: int, member_id: int) -> OrganizationMember:
    member = session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization member not found.")
    return member


def _role_or_404(
    session: Session,
    *,
    organization_id: int,
    role_id: int | None = None,
    role_key: str | None = None,
) -> OrganizationRole:
    if role_id is not None:
        row = session.get(OrganizationRole, role_id)
        if row is None or row.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Organization role not found.")
        return row
    assert role_key is not None
    row = session.exec(
        select(OrganizationRole)
        .where(OrganizationRole.organization_id == organization_id)
        .where(OrganizationRole.role_key == role_key)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Organization role not found.")
    return row


def _assignment_rows_for_member(session: Session, *, member_id: int) -> list[tuple[OrganizationMembershipRole, OrganizationRole]]:
    rows = session.exec(
        select(OrganizationMembershipRole, OrganizationRole)
        .join(OrganizationRole, OrganizationMembershipRole.organization_role_id == OrganizationRole.id)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .order_by(OrganizationMembershipRole.assigned_at.asc(), OrganizationMembershipRole.id.asc())
    ).all()
    return sorted(rows, key=lambda pair: role_sort_key(pair[1].role_key))


def _to_role_response(row: OrganizationRole) -> OrganizationRoleResponse:
    permissions = ROLE_DEFINITION_BY_KEY.get(row.role_key)
    return OrganizationRoleResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        role_key=row.role_key,
        display_name=row.display_name,
        system_managed=row.system_managed,
        created_at=row.created_at,
        permission_keys=list(permissions.permission_keys if permissions is not None else ()),
    )


def _to_membership_role_response(assignment: OrganizationMembershipRole, role: OrganizationRole) -> OrganizationMembershipRoleResponse:
    permissions = ROLE_DEFINITION_BY_KEY.get(role.role_key)
    return OrganizationMembershipRoleResponse(
        id=int(assignment.id or 0),
        organization_member_id=assignment.organization_member_id,
        organization_role_id=assignment.organization_role_id,
        role_key=role.role_key,
        display_name=role.display_name,
        assigned_by_user_id=assignment.assigned_by_user_id,
        assigned_at=assignment.assigned_at,
        permission_keys=list(permissions.permission_keys if permissions is not None else ()),
    )


def _to_permission_audit_response(row: OrganizationPermissionAudit) -> OrganizationPermissionAuditResponse:
    return OrganizationPermissionAuditResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        target_user_id=row.target_user_id,
        action_key=row.action_key,
        permission_result=row.permission_result,
        evaluation_context_json=dict(sorted((row.evaluation_context_json or {}).items())),
        created_at=row.created_at,
    )


def resolve_user_organization_roles(session: Session, *, organization_id: int, user_id: int) -> tuple[OrganizationMembershipRoleResponse, ...]:
    member = _active_member_or_none(session, organization_id=organization_id, user_id=user_id)
    if member is None:
        return tuple()
    rows = _assignment_rows_for_member(session, member_id=int(member.id or 0))
    return tuple(_to_membership_role_response(assignment, role) for assignment, role in rows)


def evaluate_permission(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_key: str,
    target_user_id: int | None = None,
    evaluation_context_json: dict[str, Any] | None = None,
) -> PermissionEvaluation:
    get_organization_or_404(session, organization_id=organization_id)
    member = _active_member_or_none(session, organization_id=organization_id, user_id=actor_user_id)
    role_assignments = tuple()
    role_keys: tuple[str, ...] = tuple()
    permission_keys: tuple[str, ...] = tuple()
    allowed = False
    reason = "deny_by_default"

    if member is None:
        reason = "membership_required"
    else:
        role_assignments = resolve_user_organization_roles(session, organization_id=organization_id, user_id=actor_user_id)
        role_keys = tuple(row.role_key for row in role_assignments)
        permission_keys = resolve_permission_keys(role_keys)
        if action_key in permission_keys:
            allowed = True
            reason = "permission_granted"
        else:
            reason = "permission_missing"

    evaluation = PermissionEvaluation(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=action_key,
        target_user_id=target_user_id,
        allowed=allowed,
        role_keys=role_keys,
        permission_keys=permission_keys,
        reason=reason,
    )
    _audit_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action_key=action_key,
        permission_result=GRANTED_RESULT if allowed else DENIED_RESULT,
        evaluation_context_json={
            "action_key": action_key,
            "allowed": allowed,
            "permission_keys": list(permission_keys),
            "reason": reason,
            "role_keys": list(role_keys),
            **(evaluation_context_json or {}),
        },
    )
    session.commit()
    return evaluation


def validate_org_access(session: Session, *, organization_id: int, actor_user_id: int) -> OrganizationActorContext:
    context = resolve_organization_context(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if context.member is None:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=actor_user_id,
            action_key="organization:membership",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "membership_required"},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Organization membership is required.")
    return context


def validate_org_permission(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_key: str,
    target_user_id: int | None = None,
    evaluation_context_json: dict[str, Any] | None = None,
) -> PermissionEvaluation:
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=action_key,
        target_user_id=target_user_id,
        evaluation_context_json=evaluation_context_json,
    )
    if not evaluation.allowed:
        raise HTTPException(status_code=403, detail=f"Missing required permission: {action_key}")
    return evaluation


def list_organization_roles(
    session: Session,
    *,
    organization_id: int,
    limit: int,
    offset: int,
) -> OrganizationRoleListResponse:
    roles = ensure_system_roles(session, organization_id=organization_id)
    items = [_to_role_response(row) for row in roles]
    return OrganizationRoleListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def list_member_roles(
    session: Session,
    *,
    organization_id: int,
    member_id: int,
    limit: int,
    offset: int,
) -> OrganizationMembershipRoleListResponse:
    member = _member_in_organization_or_404(session, organization_id=organization_id, member_id=member_id)
    items = [_to_membership_role_response(assignment, role) for assignment, role in _assignment_rows_for_member(session, member_id=int(member.id or 0))]
    return OrganizationMembershipRoleListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def list_permission_audits(
    session: Session,
    *,
    organization_id: int,
    limit: int,
    offset: int,
) -> OrganizationPermissionAuditListResponse:
    stmt = constrain_query_to_organization(select(OrganizationPermissionAudit), OrganizationPermissionAudit, organization_id=organization_id)
    rows = session.exec(stmt.order_by(OrganizationPermissionAudit.created_at.asc(), OrganizationPermissionAudit.id.asc())).all()
    items = [_to_permission_audit_response(row) for row in rows]
    return OrganizationPermissionAuditListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def assign_role(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    member_id: int,
    role_key: str,
) -> tuple[OrganizationMembershipRoleResponse, bool]:
    role_key = role_key.strip().lower()
    target_member = _member_in_organization_or_404(session, organization_id=organization_id, member_id=member_id)
    role = _role_or_404(session, organization_id=organization_id, role_key=role_key)
    organization = get_organization_or_404(session, organization_id=organization_id)
    validate_org_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="members:roles:update",
        target_user_id=target_member.user_id,
        evaluation_context_json={"operation": "assign_role", "role_key": role_key},
    )

    if actor_user_id == target_member.user_id:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:assign",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "self_escalation_denied", "role_key": role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Users cannot change their own organization roles.")
    if target_member.user_id == organization.owner_user_id:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:assign",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "owner_role_protected", "role_key": role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Owner roles are immutable in this phase.")
    if role_key in {"owner", "admin"} and actor_user_id != organization.owner_user_id:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:assign",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "restricted_role_assignment", "role_key": role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Only organization owners can assign this role.")

    existing = session.exec(
        select(OrganizationMembershipRole)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .where(OrganizationMembershipRole.organization_role_id == int(role.id or 0))
    ).first()
    if existing is not None:
        return _to_membership_role_response(existing, role), False

    assignment = OrganizationMembershipRole(
        organization_member_id=member_id,
        organization_role_id=int(role.id or 0),
        assigned_by_user_id=actor_user_id,
    )
    session.add(assignment)
    session.flush()
    _audit_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_user_id=target_member.user_id,
        action_key="role:assign",
        permission_result=ASSIGNED_RESULT,
        evaluation_context_json={"member_id": member_id, "role_key": role_key},
    )
    from app.services.activity_feed_integration import record_permissions_activity

    record_permissions_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_kind="role_assigned",
        payload={
            "title": "Role assigned",
            "body": f"Role '{role_key}' was assigned to member {member_id}.",
            "member_id": member_id,
            "role_key": role_key,
            "target_user_id": target_member.user_id,
        },
        notify_user_id=int(target_member.user_id),
    )
    from app.services.audit_ledger_integration import record_permissions_audit

    record_permissions_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="role_assigned",
        resource_type="organization_member_role",
        resource_id=f"{member_id}:{role_key}",
        payload={
            "member_id": member_id,
            "role_key": role_key,
            "target_user_id": target_member.user_id,
        },
    )
    session.commit()
    session.refresh(assignment)
    return _to_membership_role_response(assignment, role), True


def remove_role(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    member_id: int,
    role_id: int,
) -> OrganizationMembershipRoleResponse:
    target_member = _member_in_organization_or_404(session, organization_id=organization_id, member_id=member_id)
    assignment = session.exec(
        select(OrganizationMembershipRole)
        .where(OrganizationMembershipRole.organization_member_id == member_id)
        .where(OrganizationMembershipRole.organization_role_id == role_id)
    ).first()
    role = _role_or_404(session, organization_id=organization_id, role_id=role_id)
    organization = get_organization_or_404(session, organization_id=organization_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Organization role assignment not found.")

    validate_org_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="members:roles:update",
        target_user_id=target_member.user_id,
        evaluation_context_json={"operation": "remove_role", "role_key": role.role_key},
    )
    if target_member.user_id == organization.owner_user_id or role.role_key == "owner":
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:remove",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "owner_role_protected", "role_key": role.role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Owner role assignments are immutable in this phase.")
    if actor_user_id == target_member.user_id:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:remove",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "self_role_mutation_denied", "role_key": role.role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Users cannot change their own organization roles.")
    if role.role_key == "admin" and actor_user_id != organization.owner_user_id:
        _audit_permission(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_member.user_id,
            action_key="role:remove",
            permission_result=DENIED_RESULT,
            evaluation_context_json={"reason": "restricted_role_removal", "role_key": role.role_key},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Only organization owners can remove this role.")

    response = _to_membership_role_response(assignment, role)
    session.delete(assignment)
    _audit_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_user_id=target_member.user_id,
        action_key="role:remove",
        permission_result=REMOVED_RESULT,
        evaluation_context_json={"member_id": member_id, "role_key": role.role_key},
    )
    from app.services.audit_ledger_integration import record_permissions_audit

    record_permissions_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="role_removed",
        resource_type="organization_member_role",
        resource_id=f"{member_id}:{role.role_key}",
        payload={
            "member_id": member_id,
            "role_key": role.role_key,
            "target_user_id": target_member.user_id,
        },
    )
    session.commit()
    return response
