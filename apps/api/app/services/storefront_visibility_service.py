from __future__ import annotations

import re

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DealerProfile, DealerStorefrontEvent, DealerStorefrontSettings, OrganizationMember
from app.services.authorization_service import evaluate_permission, validate_org_access

ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
PUBLIC_VISIBILITY = "PUBLIC"
UNLISTED_VISIBILITY = "UNLISTED"
PRIVATE_VISIBILITY = "PRIVATE"
ACTIVE_PROFILE_STATUS = "ACTIVE"
MANAGE_PERMISSION = "organization:update"


def normalize_storefront_slug(raw_slug: str) -> str:
    slug = raw_slug.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) < 2:
        raise HTTPException(status_code=400, detail="Storefront slug must be at least 2 characters.")
    return slug[:120]


def _settings_for_org(session: Session, *, organization_id: int) -> DealerStorefrontSettings | None:
    return session.exec(
        select(DealerStorefrontSettings).where(DealerStorefrontSettings.organization_id == organization_id)
    ).first()


def _profile_for_org(session: Session, *, organization_id: int) -> DealerProfile | None:
    return session.exec(select(DealerProfile).where(DealerProfile.organization_id == organization_id)).first()


def _active_member_user_ids(session: Session, *, organization_id: int) -> tuple[int, ...]:
    rows = session.exec(
        select(OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
        .order_by(OrganizationMember.user_id.asc())
    ).all()
    return tuple(int(row) for row in rows)


def _record_unauthorized_storefront_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    reason: str,
    action_key: str,
) -> None:
    audit_session = Session(session.get_bind())
    try:
        audit_session.add(
            DealerStorefrontEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                event_type="unauthorized_storefront_access_attempt",
                event_payload_json={"reason": reason, "action_key": action_key},
            )
        )
        audit_session.commit()
    finally:
        audit_session.close()


def validate_storefront_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action_key: str = MANAGE_PERMISSION,
) -> None:
    validate_org_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=action_key,
    )
    if not evaluation.allowed:
        _record_unauthorized_storefront_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason=evaluation.reason,
            action_key=action_key,
        )
        raise HTTPException(status_code=403, detail="Storefront management access denied.")


def validate_storefront_visibility(
    session: Session,
    *,
    organization_id: int,
    require_public: bool = True,
) -> tuple[DealerProfile, DealerStorefrontSettings]:
    profile = _profile_for_org(session, organization_id=organization_id)
    settings = _settings_for_org(session, organization_id=organization_id)
    if profile is None or settings is None:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    if profile.profile_status != ACTIVE_PROFILE_STATUS:
        raise HTTPException(status_code=404, detail="Storefront is not active.")
    if require_public and settings.storefront_visibility not in {PUBLIC_VISIBILITY, UNLISTED_VISIBILITY}:
        raise HTTPException(status_code=404, detail="Storefront is not publicly visible.")
    if require_public and not settings.public_inventory_enabled:
        raise HTTPException(status_code=404, detail="Public inventory is disabled for this storefront.")
    return profile, settings


def resolve_public_inventory_visibility(
    session: Session,
    *,
    organization_id: int,
) -> tuple[int, ...]:
    validate_storefront_visibility(session, organization_id=organization_id, require_public=True)
    member_ids = _active_member_user_ids(session, organization_id=organization_id)
    if not member_ids:
        return tuple()
    from app.models import InventoryCopy

    rows = session.exec(
        select(InventoryCopy.id)
        .where(InventoryCopy.user_id.in_(member_ids))
        .order_by(InventoryCopy.id.asc())
    ).all()
    return tuple(int(row) for row in rows if row is not None)


def resolve_featured_inventory(
    session: Session,
    *,
    organization_id: int,
    visible_inventory_ids: tuple[int, ...],
    settings: DealerStorefrontSettings,
) -> tuple[int, ...]:
    if not visible_inventory_ids:
        return tuple()
    limit = min(max(int(settings.featured_inventory_limit), 1), 100)
    sort_mode = settings.featured_inventory_sort
    manual_ids = [int(value) for value in (settings.featured_manual_inventory_ids_json or [])]
    visible_set = set(visible_inventory_ids)

    if sort_mode == "manually_selected":
        ordered = [inv_id for inv_id in manual_ids if inv_id in visible_set]
        return tuple(ordered[:limit])

    from app.models import InventoryCopy
    from app.services.inventory_canonical_spine import apply_inventory_spine_joins

    stmt = apply_inventory_spine_joins(
        select(InventoryCopy.id)
        .select_from(InventoryCopy)
        .where(InventoryCopy.id.in_(tuple(sorted(visible_set))))
    )
    if sort_mode == "newest":
        stmt = stmt.order_by(InventoryCopy.created_at.desc(), InventoryCopy.id.desc())
    elif sort_mode == "recently_updated":
        stmt = stmt.order_by(InventoryCopy.received_at.desc(), InventoryCopy.id.desc())
    elif sort_mode == "highest_value":
        stmt = stmt.order_by(InventoryCopy.current_fmv.desc(), InventoryCopy.id.desc())
    else:
        stmt = stmt.order_by(InventoryCopy.id.asc())
    rows = session.exec(stmt.limit(limit)).all()
    return tuple(int(row) for row in rows)
