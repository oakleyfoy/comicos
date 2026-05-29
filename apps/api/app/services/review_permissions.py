from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import OrganizationMember, OrganizationReview, OrganizationReviewEvent
from app.security.tenant_context import get_membership_record, get_organization_or_404
from app.services.authorization_service import evaluate_permission, validate_org_access
from app.services.organization_inventory_access import validate_org_inventory_membership

ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"
VIEW_PERMISSION = "operations:view"
MANAGE_PERMISSION = "operations:manage"


@dataclass(frozen=True)
class ReviewPermissionResolution:
    can_view: bool
    can_create: bool
    can_assign: bool
    can_approve: bool
    can_reject: bool
    can_complete: bool
    can_move_queue: bool
    reason: str


def _record_unauthorized_review_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int | None,
    inventory_item_id: int | None,
    reason: str,
    action_key: str,
) -> None:
    session.add(
        OrganizationReviewEvent(
            organization_id=organization_id,
            organization_review_id=organization_review_id,
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_review_access_attempt",
            event_payload_json={"reason": reason, "action_key": action_key},
        )
    )
    session.flush()


def resolve_review_permissions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> ReviewPermissionResolution:
    validate_org_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    view_eval = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=VIEW_PERMISSION,
    )
    manage_eval = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=MANAGE_PERMISSION,
    )
    if not view_eval.allowed:
        return ReviewPermissionResolution(
            can_view=False,
            can_create=False,
            can_assign=False,
            can_approve=False,
            can_reject=False,
            can_complete=False,
            can_move_queue=False,
            reason=view_eval.reason,
        )
    allowed = manage_eval.allowed
    return ReviewPermissionResolution(
        can_view=True,
        can_create=allowed,
        can_assign=allowed,
        can_approve=allowed,
        can_reject=allowed,
        can_complete=allowed,
        can_move_queue=allowed,
        reason="granted" if allowed else manage_eval.reason,
    )


def validate_review_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> None:
    validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=VIEW_PERMISSION,
    )


def validate_review_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int | None = None,
    inventory_item_id: int | None = None,
    action_key: str = VIEW_PERMISSION,
) -> OrganizationReview | None:
    organization = get_organization_or_404(session, organization_id=organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        _record_unauthorized_review_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            organization_review_id=organization_review_id,
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
        _record_unauthorized_review_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            organization_review_id=organization_review_id,
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
        _record_unauthorized_review_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            organization_review_id=organization_review_id,
            inventory_item_id=inventory_item_id,
            reason=evaluation.reason,
            action_key=action_key,
        )
        raise HTTPException(status_code=403, detail="Organization review access denied.")
    review: OrganizationReview | None = None
    if organization_review_id is not None:
        review = session.get(OrganizationReview, organization_review_id)
        if review is None or int(review.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Review not found.")
        inventory_item_id = int(review.inventory_item_id)
    if inventory_item_id is not None:
        validate_org_inventory_membership(
            session,
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
        )
    return review


def validate_review_assignment(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
    assigned_user_id: int,
) -> OrganizationReview:
    review = validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        action_key=MANAGE_PERMISSION,
    )
    assert review is not None
    member = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == assigned_user_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
    ).first()
    if member is None:
        raise HTTPException(status_code=400, detail="Assigned user must be an active organization member.")
    return review


def validate_review_queue_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    review_id: int,
) -> OrganizationReview:
    review = validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=review_id,
        action_key=MANAGE_PERMISSION,
    )
    assert review is not None
    return review
