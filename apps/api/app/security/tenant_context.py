from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Organization, OrganizationMember


@dataclass(frozen=True)
class OrganizationActorContext:
    organization: Organization
    actor_user_id: int
    member: OrganizationMember | None


def get_organization_or_404(session: Session, *, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


def get_membership_record(
    session: Session,
    *,
    organization_id: int,
    user_id: int,
    active_only: bool = False,
) -> OrganizationMember | None:
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user_id)
        .order_by(OrganizationMember.joined_at.asc(), OrganizationMember.id.asc())
    )
    row = session.exec(stmt).first()
    if row is None:
        return None
    if active_only and row.membership_status != "ACTIVE":
        return None
    return row


def resolve_organization_context(session: Session, *, organization_id: int, actor_user_id: int) -> OrganizationActorContext:
    organization = get_organization_or_404(session, organization_id=organization_id)
    member = get_membership_record(session, organization_id=organization_id, user_id=actor_user_id, active_only=True)
    return OrganizationActorContext(organization=organization, actor_user_id=actor_user_id, member=member)


def require_active_membership(context: OrganizationActorContext) -> OrganizationMember:
    if context.member is None:
        raise HTTPException(status_code=403, detail="Organization membership is required.")
    return context.member


def require_owner(context: OrganizationActorContext) -> None:
    if context.organization.owner_user_id != context.actor_user_id:
        raise HTTPException(status_code=403, detail="Organization owner access is required.")


def ensure_organization_scope(*, expected_organization_id: int, actual_organization_id: int) -> None:
    if expected_organization_id != actual_organization_id:
        raise HTTPException(status_code=403, detail="Cross-organization access is not allowed.")


def constrain_query_to_organization(statement: Any, model: type[Any], *, organization_id: int) -> Any:
    if not hasattr(model, "organization_id"):
        raise TypeError(f"{model.__name__} does not expose organization_id for tenant scoping.")
    return statement.where(getattr(model, "organization_id") == organization_id)
