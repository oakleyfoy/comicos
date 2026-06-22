from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import DealerProfile, DealerStorefrontEvent, DealerStorefrontSettings, InventoryCopy
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    cover_name_expr,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.dealer_storefront import (
    DealerProfileResponse,
    DealerProfileUpsertRequest,
    DealerStorefrontSettingsResponse,
    DealerStorefrontSettingsUpdateRequest,
    PublicStorefrontInventoryItem,
    PublicStorefrontInventoryListResponse,
    PublicStorefrontResponse,
)
from app.services.storefront_visibility_service import (
    normalize_storefront_slug,
    resolve_featured_inventory,
    resolve_public_inventory_visibility,
    validate_storefront_access,
    validate_storefront_visibility,
)

ENGINE_VERSION = "P42-06-v1"
PROFILE_ACTIVE = "ACTIVE"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(_json_safe(payload), sort_keys=True))


def create_storefront_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any] | None = None,
) -> DealerStorefrontEvent:
    row = DealerStorefrontEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_stable_payload(event_payload_json or {}),
    )
    session.add(row)
    session.flush()
    return row


def _to_profile_response(row: DealerProfile) -> DealerProfileResponse:
    assert row.id is not None
    return DealerProfileResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        public_slug=str(row.public_slug),
        display_name=str(row.display_name),
        tagline=row.tagline,
        description=row.description,
        logo_asset_id=row.logo_asset_id,
        banner_asset_id=row.banner_asset_id,
        website_url=row.website_url,
        instagram_url=row.instagram_url,
        whatnot_url=row.whatnot_url,
        location_label=row.location_label,
        profile_status=str(row.profile_status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_settings_response(row: DealerStorefrontSettings) -> DealerStorefrontSettingsResponse:
    assert row.id is not None
    manual_ids = [int(value) for value in (row.featured_manual_inventory_ids_json or [])]
    return DealerStorefrontSettingsResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        storefront_visibility=str(row.storefront_visibility),
        public_inventory_enabled=bool(row.public_inventory_enabled),
        featured_inventory_limit=int(row.featured_inventory_limit),
        featured_inventory_sort=str(row.featured_inventory_sort),
        featured_manual_inventory_ids=manual_ids,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _project_public_rows(session: Session, *, inventory_ids: tuple[int, ...]) -> list[PublicStorefrontInventoryItem]:
    if not inventory_ids:
        return []
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                InventoryCopy.id,
                title_expr(),
                publisher_expr(),
                issue_number_expr(),
                cover_name_expr(),
                InventoryCopy.grade_status,
                InventoryCopy.current_fmv,
                InventoryCopy.release_year,
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.id.in_(inventory_ids))
        .order_by(InventoryCopy.id.asc())
    ).all()
    by_id = {
        int(row[0]): PublicStorefrontInventoryItem(
            inventory_copy_id=int(row[0]),
            title=str(row[1]),
            publisher=str(row[2]),
            issue_number=str(row[3]),
            cover_name=row[4],
            grade_status=str(row[5]),
            current_fmv=row[6],
            release_year=row[7],
        )
        for row in rows
    }
    return [by_id[inv_id] for inv_id in inventory_ids if inv_id in by_id]


def create_or_update_dealer_profile(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: DealerProfileUpsertRequest,
) -> DealerProfileResponse:
    validate_storefront_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    slug = normalize_storefront_slug(payload.public_slug)
    existing = session.exec(select(DealerProfile).where(DealerProfile.organization_id == organization_id)).first()
    slug_owner = session.exec(select(DealerProfile).where(DealerProfile.public_slug == slug)).first()
    if slug_owner is not None and (existing is None or int(slug_owner.id or 0) != int(existing.id or 0)):
        raise HTTPException(status_code=409, detail="Storefront slug is already in use.")
    created = existing is None
    if existing is None:
        existing = DealerProfile(
            organization_id=organization_id,
            public_slug=slug,
            display_name=payload.display_name.strip(),
            tagline=payload.tagline,
            description=payload.description,
            logo_asset_id=payload.logo_asset_id,
            banner_asset_id=payload.banner_asset_id,
            website_url=payload.website_url,
            instagram_url=payload.instagram_url,
            whatnot_url=payload.whatnot_url,
            location_label=payload.location_label,
            profile_status=payload.profile_status,
        )
        session.add(existing)
    else:
        existing.public_slug = slug
        existing.display_name = payload.display_name.strip()
        existing.tagline = payload.tagline
        existing.description = payload.description
        existing.logo_asset_id = payload.logo_asset_id
        existing.banner_asset_id = payload.banner_asset_id
        existing.website_url = payload.website_url
        existing.instagram_url = payload.instagram_url
        existing.whatnot_url = payload.whatnot_url
        existing.location_label = payload.location_label
        existing.profile_status = payload.profile_status
        existing.updated_at = utc_now()
        session.add(existing)
    session.flush()
    settings = session.exec(
        select(DealerStorefrontSettings).where(DealerStorefrontSettings.organization_id == organization_id)
    ).first()
    if settings is None:
        settings = DealerStorefrontSettings(
            organization_id=organization_id,
            storefront_visibility="PRIVATE",
            public_inventory_enabled=False,
            featured_inventory_limit=12,
            featured_inventory_sort="newest",
            featured_manual_inventory_ids_json=[],
        )
        session.add(settings)
        session.flush()
    create_storefront_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="storefront_created" if created else "storefront_updated",
        event_payload_json={
            "profile_id": int(existing.id or 0),
            "public_slug": slug,
            "profile_status": existing.profile_status,
            "engine_version": ENGINE_VERSION,
        },
    )
    if payload.profile_status == "DISABLED":
        create_storefront_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="storefront_disabled",
            event_payload_json={"profile_id": int(existing.id or 0), "engine_version": ENGINE_VERSION},
        )
    from app.services.activity_feed_integration import record_storefront_activity

    record_storefront_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_kind="storefront_updated" if not created else "storefront_created",
        payload={
            "title": "Storefront profile updated",
            "body": f"Storefront profile '{slug}' was updated.",
            "public_slug": slug,
            "profile_status": existing.profile_status,
        },
    )
    from app.services.audit_ledger_integration import record_storefront_audit

    record_storefront_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="storefront_profile_updated" if not created else "storefront_profile_created",
        resource_type="dealer_profile",
        resource_id=int(existing.id or 0),
        payload={
            "public_slug": slug,
            "profile_status": existing.profile_status,
        },
    )
    session.commit()
    session.refresh(existing)
    return _to_profile_response(existing)


def update_storefront_settings(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: DealerStorefrontSettingsUpdateRequest,
) -> DealerStorefrontSettingsResponse:
    validate_storefront_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    profile = session.exec(select(DealerProfile).where(DealerProfile.organization_id == organization_id)).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Create a dealer profile before updating storefront settings.")
    settings = session.exec(
        select(DealerStorefrontSettings).where(DealerStorefrontSettings.organization_id == organization_id)
    ).first()
    if settings is None:
        raise HTTPException(status_code=404, detail="Storefront settings not found.")
    previous_visibility = settings.storefront_visibility
    previous_sort = settings.featured_inventory_sort
    settings.storefront_visibility = payload.storefront_visibility
    settings.public_inventory_enabled = payload.public_inventory_enabled
    settings.featured_inventory_limit = payload.featured_inventory_limit
    settings.featured_inventory_sort = payload.featured_inventory_sort
    settings.featured_manual_inventory_ids_json = sorted(set(int(v) for v in payload.featured_manual_inventory_ids))
    settings.updated_at = utc_now()
    session.add(settings)
    session.flush()
    if previous_visibility != settings.storefront_visibility:
        create_storefront_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="storefront_visibility_changed",
            event_payload_json={
                "previous_visibility": previous_visibility,
                "storefront_visibility": settings.storefront_visibility,
                "engine_version": ENGINE_VERSION,
            },
        )
    if previous_sort != settings.featured_inventory_sort or settings.featured_manual_inventory_ids_json:
        create_storefront_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="featured_inventory_updated",
            event_payload_json={
                "featured_inventory_sort": settings.featured_inventory_sort,
                "featured_inventory_limit": settings.featured_inventory_limit,
                "featured_manual_inventory_ids": settings.featured_manual_inventory_ids_json,
                "engine_version": ENGINE_VERSION,
            },
        )
    from app.services.activity_feed_integration import record_storefront_activity

    record_storefront_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_kind="settings_updated",
        payload={
            "title": "Storefront settings updated",
            "body": "Dealer storefront visibility and featured inventory settings changed.",
            "storefront_visibility": settings.storefront_visibility,
        },
    )
    from app.services.audit_ledger_integration import record_storefront_audit

    record_storefront_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="storefront_settings_updated",
        resource_type="dealer_storefront_settings",
        resource_id=int(settings.id or 0),
        payload={
            "previous_visibility": previous_visibility,
            "storefront_visibility": settings.storefront_visibility,
            "featured_inventory_sort": settings.featured_inventory_sort,
            "featured_inventory_limit": settings.featured_inventory_limit,
        },
    )
    session.commit()
    session.refresh(settings)
    return _to_settings_response(settings)


def resolve_storefront_by_slug(session: Session, *, public_slug: str) -> PublicStorefrontResponse:
    slug = normalize_storefront_slug(public_slug)
    profile = session.exec(select(DealerProfile).where(DealerProfile.public_slug == slug)).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    settings = session.exec(
        select(DealerStorefrontSettings).where(DealerStorefrontSettings.organization_id == profile.organization_id)
    ).first()
    if settings is None:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    if profile.profile_status != PROFILE_ACTIVE:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    if settings.storefront_visibility == "PRIVATE":
        raise HTTPException(status_code=404, detail="Storefront not found.")
    return PublicStorefrontResponse(profile=_to_profile_response(profile), settings=_to_settings_response(settings))


def list_public_storefront_inventory(
    session: Session,
    *,
    public_slug: str,
    limit: int = 50,
    offset: int = 0,
) -> PublicStorefrontInventoryListResponse:
    slug = normalize_storefront_slug(public_slug)
    profile = session.exec(select(DealerProfile).where(DealerProfile.public_slug == slug)).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    validate_storefront_visibility(session, organization_id=int(profile.organization_id), require_public=True)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    visible_ids = resolve_public_inventory_visibility(session, organization_id=int(profile.organization_id))
    page_ids = visible_ids[offset : offset + limit]
    items = _project_public_rows(session, inventory_ids=tuple(page_ids))
    return PublicStorefrontInventoryListResponse(
        items=items,
        total_items=len(visible_ids),
        limit=limit,
        offset=offset,
    )


def list_featured_inventory(session: Session, *, public_slug: str) -> PublicStorefrontInventoryListResponse:
    slug = normalize_storefront_slug(public_slug)
    profile = session.exec(select(DealerProfile).where(DealerProfile.public_slug == slug)).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Storefront not found.")
    profile_row, settings = validate_storefront_visibility(
        session,
        organization_id=int(profile.organization_id),
        require_public=True,
    )
    del profile_row
    visible_ids = resolve_public_inventory_visibility(session, organization_id=int(profile.organization_id))
    featured_ids = resolve_featured_inventory(
        session,
        organization_id=int(profile.organization_id),
        visible_inventory_ids=visible_ids,
        settings=settings,
    )
    items = _project_public_rows(session, inventory_ids=featured_ids)
    return PublicStorefrontInventoryListResponse(
        items=items,
        total_items=len(items),
        limit=len(items),
        offset=0,
    )
