from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy, MarketplaceListingDraft, ShopifyProductMapping, ShopifyStorefront
from app.schemas.shopify_sync import (
    ShopifyPermissionResponse,
    ShopifyProductMappingCreateRequest,
    ShopifyProductMappingListResponse,
    ShopifyProductMappingResponse,
    ShopifyProductMappingUpdateRequest,
)
from app.services.marketplace_listing_projection import generate_marketplace_payload
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions
from app.services.shopify_publication_registry import (
    derive_publication_status,
    normalize_mapping_status,
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


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
    storefront_id: int | None = None,
) -> MarketplacePermissionResolution:
    from app.services.shopify_sync_service import create_shopify_sync_event

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
    from app.services.shopify_sync_service import create_shopify_sync_event

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


def _storefront_or_404(session: Session, *, organization_id: int, storefront_id: int) -> ShopifyStorefront:
    row = session.get(ShopifyStorefront, storefront_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Shopify storefront not found.")
    return row


def _inventory_or_404(session: Session, *, inventory_item_id: int) -> InventoryCopy:
    row = session.get(InventoryCopy, inventory_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return row


def _draft_or_404(session: Session, *, organization_id: int, marketplace_listing_draft_id: int) -> MarketplaceListingDraft:
    row = session.get(MarketplaceListingDraft, marketplace_listing_draft_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace listing draft not found.")
    return row


def _to_mapping_response(row: ShopifyProductMapping) -> ShopifyProductMappingResponse:
    return ShopifyProductMappingResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        inventory_item_id=row.inventory_item_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        storefront_product_identifier=row.storefront_product_identifier,
        mapping_status=row.mapping_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def validate_product_mapping(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    marketplace_listing_draft_id: int,
    storefront_product_identifier: str,
    mapping_status: str,
    exclude_mapping_id: int | None = None,
) -> dict[str, Any]:
    from app.services.shopify_sync_service import create_shopify_sync_event

    try:
        _inventory_or_404(session, inventory_item_id=inventory_item_id)
        _draft_or_404(session, organization_id=organization_id, marketplace_listing_draft_id=marketplace_listing_draft_id)
    except HTTPException as exc:
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=None,
            actor_user_id=actor_user_id,
            event_type="invalid_product_mapping_detected",
            event_payload_json={
                "inventory_item_id": inventory_item_id,
                "marketplace_listing_draft_id": marketplace_listing_draft_id,
                "reason": exc.detail,
            },
        )
        session.commit()
        raise

    identifier = storefront_product_identifier.strip()
    if not identifier:
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=None,
            actor_user_id=actor_user_id,
            event_type="invalid_product_mapping_detected",
            event_payload_json={
                "inventory_item_id": inventory_item_id,
                "marketplace_listing_draft_id": marketplace_listing_draft_id,
                "reason": "storefront_product_identifier_required",
            },
        )
        session.commit()
        raise HTTPException(status_code=422, detail="Shopify product identifier is required.")
    duplicate_identifier = session.exec(
        select(ShopifyProductMapping)
        .where(ShopifyProductMapping.organization_id == organization_id)
        .where(ShopifyProductMapping.storefront_product_identifier == identifier)
        .order_by(ShopifyProductMapping.id.asc())
    ).first()
    if duplicate_identifier is not None and int(duplicate_identifier.id or 0) != int(exclude_mapping_id or 0):
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=None,
            actor_user_id=actor_user_id,
            event_type="invalid_product_mapping_detected",
            event_payload_json={
                "inventory_item_id": inventory_item_id,
                "marketplace_listing_draft_id": marketplace_listing_draft_id,
                "storefront_product_identifier": identifier,
                "reason": "storefront_product_identifier_already_exists",
            },
        )
        session.commit()
        raise HTTPException(status_code=409, detail="Shopify product identifier already exists.")
    try:
        normalized_status = normalize_mapping_status(mapping_status)
    except ValueError as exc:
        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=None,
            actor_user_id=actor_user_id,
            event_type="invalid_product_mapping_detected",
            event_payload_json={
                "inventory_item_id": inventory_item_id,
                "marketplace_listing_draft_id": marketplace_listing_draft_id,
                "storefront_product_identifier": identifier,
                "reason": str(exc),
            },
        )
        session.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "storefront_product_identifier": identifier,
        "mapping_status": normalized_status,
    }


def create_product_mapping(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ShopifyProductMappingCreateRequest,
) -> ShopifyProductMappingResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_mapping:create")
    existing = session.exec(
        select(ShopifyProductMapping)
        .where(ShopifyProductMapping.organization_id == organization_id)
        .where(ShopifyProductMapping.inventory_item_id == payload.inventory_item_id)
        .where(ShopifyProductMapping.marketplace_listing_draft_id == payload.marketplace_listing_draft_id)
    ).first()
    normalized = validate_product_mapping(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=payload.inventory_item_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        storefront_product_identifier=payload.storefront_product_identifier,
        mapping_status=payload.mapping_status,
        exclude_mapping_id=int(existing.id or 0) if existing is not None else None,
    )
    if existing is None:
        row = ShopifyProductMapping(
            organization_id=organization_id,
            inventory_item_id=payload.inventory_item_id,
            marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
            storefront_product_identifier=normalized["storefront_product_identifier"],
            mapping_status=normalized["mapping_status"],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(row)
        session.flush()
        from app.services.shopify_sync_service import create_shopify_sync_event

        create_shopify_sync_event(
            session,
            organization_id=organization_id,
            storefront_id=None,
            actor_user_id=actor_user_id,
            event_type="product_mapping_created",
            event_payload_json={
                "mapping_id": int(row.id or 0),
                "storefront_product_identifier": row.storefront_product_identifier,
                "mapping_status": row.mapping_status,
            },
        )
        session.commit()
        return _to_mapping_response(row)

    if (
        existing.storefront_product_identifier == normalized["storefront_product_identifier"]
        and existing.mapping_status == normalized["mapping_status"]
    ):
        return _to_mapping_response(existing)

    existing.storefront_product_identifier = normalized["storefront_product_identifier"]
    existing.mapping_status = normalized["mapping_status"]
    existing.updated_at = utc_now()
    session.add(existing)
    session.flush()
    from app.services.shopify_sync_service import create_shopify_sync_event

    create_shopify_sync_event(
        session,
        organization_id=organization_id,
        storefront_id=None,
        actor_user_id=actor_user_id,
        event_type="product_mapping_updated",
        event_payload_json={
            "mapping_id": int(existing.id or 0),
            "storefront_product_identifier": existing.storefront_product_identifier,
            "mapping_status": existing.mapping_status,
        },
    )
    session.commit()
    return _to_mapping_response(existing)


def update_product_mapping(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    mapping_id: int,
    payload: ShopifyProductMappingUpdateRequest,
) -> ShopifyProductMappingResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_mapping:update")
    row = session.get(ShopifyProductMapping, mapping_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Shopify product mapping not found.")
    storefront_product_identifier = row.storefront_product_identifier
    mapping_status = row.mapping_status
    if payload.storefront_product_identifier is not None:
        storefront_product_identifier = payload.storefront_product_identifier.strip()
    if payload.mapping_status is not None:
        mapping_status = payload.mapping_status.strip()
    normalized = validate_product_mapping(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=row.inventory_item_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        storefront_product_identifier=storefront_product_identifier,
        mapping_status=mapping_status,
        exclude_mapping_id=int(row.id or 0),
    )
    if (
        row.storefront_product_identifier == normalized["storefront_product_identifier"]
        and row.mapping_status == normalized["mapping_status"]
    ):
        return _to_mapping_response(row)
    row.storefront_product_identifier = normalized["storefront_product_identifier"]
    row.mapping_status = normalized["mapping_status"]
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    from app.services.shopify_sync_service import create_shopify_sync_event

    create_shopify_sync_event(
        session,
        organization_id=organization_id,
        storefront_id=None,
        actor_user_id=actor_user_id,
        event_type="product_mapping_updated",
        event_payload_json={
            "mapping_id": int(row.id or 0),
            "storefront_product_identifier": row.storefront_product_identifier,
            "mapping_status": row.mapping_status,
        },
    )
    session.commit()
    return _to_mapping_response(row)


def list_product_mappings(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ShopifyProductMappingListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="shopify_mapping:view")
    base = select(ShopifyProductMapping).where(ShopifyProductMapping.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(ShopifyProductMapping.updated_at.desc(), ShopifyProductMapping.id.desc()).offset(offset).limit(limit)).all()
    return ShopifyProductMappingListResponse(
        items=[_to_mapping_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def generate_storefront_projection(
    session: Session,
    *,
    organization_id: int,
    storefront_id: int,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    from app.services.shopify_sync_service import create_shopify_sync_event

    storefront = _storefront_or_404(session, organization_id=organization_id, storefront_id=storefront_id)
    base = (
        select(ShopifyProductMapping)
        .join(MarketplaceListingDraft, ShopifyProductMapping.marketplace_listing_draft_id == MarketplaceListingDraft.id)
        .where(ShopifyProductMapping.organization_id == organization_id)
        .where(MarketplaceListingDraft.marketplace_account_id == storefront.marketplace_account_id)
    )
    mappings = session.exec(base.order_by(ShopifyProductMapping.updated_at.desc(), ShopifyProductMapping.id.desc())).all()
    mapped_rows = []
    for row in mappings:
        draft = _draft_or_404(session, organization_id=organization_id, marketplace_listing_draft_id=row.marketplace_listing_draft_id)
        projection = generate_marketplace_payload(session, marketplace_type="shopify", draft=draft)
        mapped_rows.append(
            _json_safe(
                {
                    "mapping": _to_mapping_response(row).model_dump(mode="json"),
                    "publication_status": derive_publication_status(
                        storefront_status=storefront.storefront_status,
                        mapping_status=row.mapping_status,
                    ),
                    "projection": projection,
                }
            )
        )
    payload = _json_safe(
        {
            "schema_version": "P43-08-shopify-sync-v1",
            "storefront": {
                "id": int(storefront.id or 0),
                "storefront_name": storefront.storefront_name,
                "storefront_identifier": storefront.storefront_identifier,
                "storefront_status": storefront.storefront_status,
                "marketplace_account_id": storefront.marketplace_account_id,
            },
            "items": mapped_rows,
            "total_items": len(mapped_rows),
        }
    )
    create_shopify_sync_event(
        session,
        organization_id=organization_id,
        storefront_id=storefront_id,
        actor_user_id=actor_user_id,
        event_type="storefront_projection_generated",
        event_payload_json={"total_items": len(mapped_rows), "schema_version": "P43-08-shopify-sync-v1"},
    )
    session.commit()
    assert isinstance(payload, dict)
    return payload
