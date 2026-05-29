from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    ShopifyProductMapping,
    ShopifyStorefront,
    ShopifySyncEvent,
    ShopifySyncState,
)
from app.schemas.shopify_sync import (
    ShopifyPermissionResponse,
    ShopifyStorefrontCreateRequest,
    ShopifyStorefrontListResponse,
    ShopifyStorefrontResponse,
    ShopifySyncOverviewResponse,
    ShopifySyncSnapshotResponse,
    ShopifySyncStateListResponse,
    ShopifySyncStateResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions
from app.services.shopify_publication_registry import (
    normalize_publication_status,
    normalize_sync_status,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> ShopifyPermissionResponse:
    return ShopifyPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _storefront_or_404(session: Session, *, organization_id: int, storefront_id: int) -> ShopifyStorefront:
    row = session.get(ShopifyStorefront, storefront_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Shopify storefront not found.")
    return row


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    row = session.get(MarketplaceAccount, marketplace_account_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return row


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
    storefront_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=storefront_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_shopify_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Shopify visibility is denied for this organization.")
    return resolution


def _validate_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
    storefront_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=storefront_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_shopify_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Shopify management is denied for this organization.")
    return resolution


def _to_storefront_response(row: ShopifyStorefront) -> ShopifyStorefrontResponse:
    return ShopifyStorefrontResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        storefront_name=row.storefront_name,
        storefront_status=row.storefront_status,
        storefront_identifier=row.storefront_identifier,
        created_at=row.created_at,
    )


def _to_sync_state_response(row: ShopifySyncState) -> ShopifySyncStateResponse:
    return ShopifySyncStateResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        storefront_id=row.storefront_id,
        sync_status=row.sync_status,
        sync_payload_json=dict(row.sync_payload_json or {}),
        last_sync_at=row.last_sync_at,
        created_at=row.created_at,
    )


def create_shopify_sync_event(
    session: Session,
    *,
    organization_id: int,
    storefront_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> ShopifySyncEvent:
    row = ShopifySyncEvent(
        organization_id=organization_id,
        storefront_id=storefront_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def create_storefront(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ShopifyStorefrontCreateRequest,
) -> ShopifyStorefrontResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_storefront:create")
    _account_or_404(session, organization_id=organization_id, marketplace_account_id=payload.marketplace_account_id)
    try:
        storefront_status = normalize_publication_status(payload.storefront_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = ShopifyStorefront(
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        storefront_name=payload.storefront_name.strip(),
        storefront_status=storefront_status,
        storefront_identifier=payload.storefront_identifier.strip(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_shopify_sync_event(
        session,
        organization_id=organization_id,
        storefront_id=int(row.id or 0),
        actor_user_id=actor_user_id,
        event_type="storefront_created",
        event_payload_json={
            "storefront_name": row.storefront_name,
            "storefront_status": row.storefront_status,
            "storefront_identifier": row.storefront_identifier,
        },
    )
    session.commit()
    return _to_storefront_response(row)


def register_sync_state(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    storefront_id: int,
    sync_payload_json: dict[str, Any],
    sync_status: str = "pending",
) -> ShopifySyncStateResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="shopify_sync_state:register",
        storefront_id=storefront_id,
    )
    storefront = _storefront_or_404(session, organization_id=organization_id, storefront_id=storefront_id)
    try:
        normalized_status = normalize_sync_status(sync_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = session.exec(select(ShopifySyncState).where(ShopifySyncState.storefront_id == storefront_id)).first()
    payload = _json_safe(sync_payload_json)
    if row is None:
        row = ShopifySyncState(
            organization_id=organization_id,
            storefront_id=storefront.id or storefront_id,
            sync_status=normalized_status,
            sync_payload_json=payload,
            last_sync_at=utc_now(),
            created_at=utc_now(),
        )
        session.add(row)
    else:
        row.sync_status = normalized_status
        row.sync_payload_json = payload
        row.last_sync_at = utc_now()
        session.add(row)
    session.flush()
    session.commit()
    return _to_sync_state_response(row)


def list_storefronts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ShopifyStorefrontListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_storefront:view")
    base = select(ShopifyStorefront).where(ShopifyStorefront.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(ShopifyStorefront.created_at.asc(), ShopifyStorefront.id.asc()).offset(offset).limit(limit)).all()
    return ShopifyStorefrontListResponse(
        items=[_to_storefront_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_sync_states(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ShopifySyncStateListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_sync_state:view")
    base = select(ShopifySyncState).where(ShopifySyncState.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(ShopifySyncState.last_sync_at.desc(), ShopifySyncState.id.desc()).offset(offset).limit(limit)).all()
    return ShopifySyncStateListResponse(
        items=[_to_sync_state_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def generate_storefront_sync_snapshot(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    storefront_id: int,
) -> ShopifySyncSnapshotResponse:
    from app.services.shopify_mapping_service import generate_storefront_projection, list_product_mappings

    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="shopify_sync_snapshot:generate",
        storefront_id=storefront_id,
    )
    storefront = _storefront_or_404(session, organization_id=organization_id, storefront_id=storefront_id)
    projection_payload = generate_storefront_projection(
        session,
        organization_id=organization_id,
        storefront_id=storefront_id,
        actor_user_id=actor_user_id,
    )
    sync_state = register_sync_state(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        storefront_id=storefront_id,
        sync_payload_json=projection_payload,
        sync_status="completed",
    )
    create_shopify_sync_event(
        session,
        organization_id=organization_id,
        storefront_id=storefront_id,
        actor_user_id=actor_user_id,
        event_type="sync_snapshot_generated",
        event_payload_json={"snapshot_keys": sorted(projection_payload.keys())},
    )
    session.commit()
    mappings = list_product_mappings(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        limit=200,
        offset=0,
    ).items
    return ShopifySyncSnapshotResponse(
        storefront=_to_storefront_response(storefront),
        sync_state=sync_state,
        projection_payload_json=projection_payload,
        mappings=mappings,
    )


def get_shopify_overview(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> ShopifySyncOverviewResponse:
    from app.services.shopify_mapping_service import list_product_mappings

    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_overview:view")
    storefronts = list_storefronts(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=200, offset=0)
    mappings = list_product_mappings(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=200, offset=0)
    sync_states = list_sync_states(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=200, offset=0)
    summary = {
        "storefront_count": storefronts.total_items,
        "mapped_items": sum(1 for row in mappings.items if row.mapping_status == "mapped"),
        "invalid_items": sum(1 for row in mappings.items if row.mapping_status == "invalid"),
        "sync_states": sync_states.total_items,
    }
    return ShopifySyncOverviewResponse(
        permissions=_permission_response(resolution),
        storefronts=storefronts.items,
        mappings=mappings.items,
        sync_states=sync_states.items,
        summary=summary,
    )
