from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy, OrganizationMember, OrganizationInventoryWorkflowEvent
from app.security.tenant_context import get_membership_record, get_organization_or_404
from app.services.authorization_service import evaluate_permission, validate_org_access

ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"


@dataclass(frozen=True)
class AssignmentPermissionResolution:
    can_view: bool
    can_assign: bool
    can_unassign: bool
    can_complete: bool
    can_move_queue: bool
    reason: str


def _active_member_user_ids(session: Session, *, organization_id: int) -> tuple[int, ...]:
    rows = session.exec(
        select(OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
        .order_by(OrganizationMember.user_id.asc())
    ).all()
    return tuple(int(row) for row in rows)


def validate_org_inventory_membership(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> InventoryCopy:
    inventory = session.get(InventoryCopy, inventory_item_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    owner_user_id = inventory.user_id
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail="Inventory item is not organization scoped.")
    member_ids = _active_member_user_ids(session, organization_id=organization_id)
    if int(owner_user_id) not in member_ids:
        raise HTTPException(status_code=403, detail="Inventory item is outside organization scope.")
    return inventory


def resolve_inventory_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> tuple[int, ...]:
    validate_org_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="inventory:view",
    )
    if not evaluation.allowed:
        raise HTTPException(status_code=403, detail="Organization inventory view permission denied.")
    member_ids = _active_member_user_ids(session, organization_id=organization_id)
    if not member_ids:
        return tuple()
    rows = session.exec(
        select(InventoryCopy.id)
        .where(InventoryCopy.user_id.in_(member_ids))
        .order_by(InventoryCopy.id.asc())
    ).all()
    return tuple(int(row) for row in rows if row is not None)


def resolve_assignment_permissions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> AssignmentPermissionResolution:
    validate_org_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    view_eval = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="inventory:view",
    )
    update_eval = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="inventory:update",
    )
    if not view_eval.allowed:
        return AssignmentPermissionResolution(
            can_view=False,
            can_assign=False,
            can_unassign=False,
            can_complete=False,
            can_move_queue=False,
            reason=view_eval.reason,
        )
    return AssignmentPermissionResolution(
        can_view=True,
        can_assign=update_eval.allowed,
        can_unassign=update_eval.allowed,
        can_complete=update_eval.allowed,
        can_move_queue=update_eval.allowed,
        reason="granted" if update_eval.allowed else update_eval.reason,
    )


def _record_unauthorized_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int | None,
    reason: str,
    action_key: str,
) -> None:
    session.add(
        OrganizationInventoryWorkflowEvent(
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            workflow_event_type="unauthorized_inventory_access_attempt",
            workflow_payload_json={
                "reason": reason,
                "action_key": action_key,
            },
        )
    )
    session.flush()


def validate_shared_inventory_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int | None = None,
    action_key: str = "inventory:view",
) -> None:
    organization = get_organization_or_404(session, organization_id=organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            inventory_item_id=inventory_item_id,
            reason="organization_not_active",
            action_key=action_key,
        )
        raise HTTPException(status_code=409, detail="Organization is not active.")
    member = get_membership_record(
        session,
        organization_id=organization_id,
        user_id=actor_user_id,
        active_only=True,
    )
    if member is None:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            inventory_item_id=inventory_item_id,
            reason="membership_required",
            action_key=action_key,
        )
        raise HTTPException(status_code=403, detail="Organization membership is required.")
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=action_key,
    )
    if not evaluation.allowed:
        _record_unauthorized_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            inventory_item_id=inventory_item_id,
            reason=evaluation.reason,
            action_key=action_key,
        )
        raise HTTPException(status_code=403, detail="Organization inventory access denied.")
    if inventory_item_id is not None:
        validate_org_inventory_membership(
            session,
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
        )


def validate_inventory_assignment_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
) -> None:
    validate_shared_inventory_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
        action_key="inventory:update",
    )
    assigned_member = get_membership_record(
        session,
        organization_id=organization_id,
        user_id=actor_user_id,
        active_only=True,
    )
    if assigned_member is None:
        raise HTTPException(status_code=403, detail="Organization membership is required.")
