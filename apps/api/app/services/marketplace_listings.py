from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy
from app.models.marketplace_listing import (
    MarketplaceListing,
    MarketplaceListingImage,
    MarketplaceListingMapping,
    MarketplaceListingPrice,
    MarketplaceListingStatusHistory,
    MarketplaceListingVariant,
)
from app.schemas.marketplace_listing import (
    MarketplaceListingCreate,
    MarketplaceListingDetail,
    MarketplaceListingImageRead,
    MarketplaceListingListResponse,
    MarketplaceListingMappingRead,
    MarketplaceListingPriceRead,
    MarketplaceListingRead,
    MarketplaceListingStatusHistoryRead,
    MarketplaceListingUpdate,
    MarketplaceListingVariantRead,
)

LISTING_STATUS_DRAFT = "DRAFT"
LISTING_STATUS_READY_TO_PUBLISH = "READY_TO_PUBLISH"
LISTING_STATUS_ARCHIVED = "ARCHIVED"
LISTING_STATUSES = {
    LISTING_STATUS_DRAFT,
    LISTING_STATUS_READY_TO_PUBLISH,
    LISTING_STATUS_ARCHIVED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _normalize_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in LISTING_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported marketplace listing status.")
    return normalized


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="Currency is required.")
    return normalized


def _ensure_inventory_access(session: Session, *, owner_id: int, inventory_copy_id: int | None) -> None:
    if inventory_copy_id is None:
        return
    inventory = session.get(InventoryCopy, inventory_copy_id)
    if inventory is None or int((inventory.user_id or 0)) != owner_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")


def _listing_read(row: MarketplaceListing) -> MarketplaceListingRead:
    return MarketplaceListingRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        inventory_copy_id=row.inventory_copy_id,
        listing_uuid=row.listing_uuid,
        listing_title=row.listing_title,
        listing_description=row.listing_description,
        listing_type=row.listing_type,
        condition_label=row.condition_label,
        grade_label=row.grade_label,
        asking_price=row.asking_price,
        currency=row.currency,
        quantity=row.quantity,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _variant_reads(session: Session, *, listing_id: int) -> list[MarketplaceListingVariantRead]:
    rows = session.exec(
        select(MarketplaceListingVariant)
        .where(MarketplaceListingVariant.listing_id == listing_id)
        .order_by(MarketplaceListingVariant.created_at.asc(), MarketplaceListingVariant.id.asc())
    ).all()
    return [
        MarketplaceListingVariantRead(
            id=int(row.id or 0),
            listing_id=row.listing_id,
            variant_code=row.variant_code,
            variant_name=row.variant_name,
            sku=row.sku,
            quantity=row.quantity,
            price=row.price,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def _image_reads(session: Session, *, listing_id: int) -> list[MarketplaceListingImageRead]:
    rows = session.exec(
        select(MarketplaceListingImage)
        .where(MarketplaceListingImage.listing_id == listing_id)
        .order_by(
            MarketplaceListingImage.is_primary.desc(),
            MarketplaceListingImage.sort_order.asc(),
            MarketplaceListingImage.id.asc(),
        )
    ).all()
    return [
        MarketplaceListingImageRead(
            id=int(row.id or 0),
            listing_id=row.listing_id,
            image_url=row.image_url,
            image_type=row.image_type,
            sort_order=row.sort_order,
            is_primary=row.is_primary,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _price_reads(session: Session, *, listing_id: int) -> list[MarketplaceListingPriceRead]:
    rows = session.exec(
        select(MarketplaceListingPrice)
        .where(MarketplaceListingPrice.listing_id == listing_id)
        .order_by(MarketplaceListingPrice.effective_at.desc(), MarketplaceListingPrice.id.desc())
    ).all()
    return [
        MarketplaceListingPriceRead(
            id=int(row.id or 0),
            listing_id=row.listing_id,
            price_type=row.price_type,
            amount=row.amount,
            currency=row.currency,
            effective_at=row.effective_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _status_history_reads(session: Session, *, listing_id: int) -> list[MarketplaceListingStatusHistoryRead]:
    rows = session.exec(
        select(MarketplaceListingStatusHistory)
        .where(MarketplaceListingStatusHistory.listing_id == listing_id)
        .order_by(MarketplaceListingStatusHistory.changed_at.asc(), MarketplaceListingStatusHistory.id.asc())
    ).all()
    return [
        MarketplaceListingStatusHistoryRead(
            id=int(row.id or 0),
            listing_id=row.listing_id,
            previous_status=row.previous_status,
            new_status=row.new_status,
            reason=row.reason,
            changed_at=row.changed_at,
        )
        for row in rows
    ]


def _mapping_reads(session: Session, *, listing_id: int) -> list[MarketplaceListingMappingRead]:
    rows = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .order_by(MarketplaceListingMapping.created_at.asc(), MarketplaceListingMapping.id.asc())
    ).all()
    return [
        MarketplaceListingMappingRead(
            id=int(row.id or 0),
            listing_id=row.listing_id,
            marketplace_id=row.marketplace_id,
            marketplace_account_id=row.marketplace_account_id,
            external_listing_id=row.external_listing_id,
            external_url=row.external_url,
            sync_status=row.sync_status,
            last_synced_at=row.last_synced_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def _detail(session: Session, row: MarketplaceListing) -> MarketplaceListingDetail:
    listing_id = int(row.id or 0)
    return MarketplaceListingDetail(
        listing=_listing_read(row),
        variants=_variant_reads(session, listing_id=listing_id),
        images=_image_reads(session, listing_id=listing_id),
        prices=_price_reads(session, listing_id=listing_id),
        status_history=_status_history_reads(session, listing_id=listing_id),
        mappings=_mapping_reads(session, listing_id=listing_id),
    )


def _listing_or_404(session: Session, *, listing_id: int) -> MarketplaceListing:
    row = session.get(MarketplaceListing, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace listing not found.")
    return row


def _owner_listing_or_404(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceListing:
    row = _listing_or_404(session, listing_id=listing_id)
    if row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace listing not found.")
    return row


def _replace_variants(session: Session, *, listing_id: int, variants: list) -> None:
    existing_rows = session.exec(
        select(MarketplaceListingVariant).where(MarketplaceListingVariant.listing_id == listing_id)
    ).all()
    for row in existing_rows:
        session.delete(row)
    session.flush()
    now = utc_now()
    for variant in variants:
        session.add(
            MarketplaceListingVariant(
                listing_id=listing_id,
                variant_code=variant.variant_code.strip(),
                variant_name=variant.variant_name.strip(),
                sku=variant.sku.strip() if variant.sku else None,
                quantity=variant.quantity,
                price=variant.price,
                created_at=now,
                updated_at=now,
            )
        )


def _append_status_history(
    session: Session,
    *,
    listing_id: int,
    previous_status: str | None,
    new_status: str,
    reason: str | None,
) -> None:
    session.add(
        MarketplaceListingStatusHistory(
            listing_id=listing_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            changed_at=utc_now(),
        )
    )


def create_listing(session: Session, *, owner_id: int, payload: MarketplaceListingCreate) -> MarketplaceListingDetail:
    _ensure_inventory_access(session, owner_id=owner_id, inventory_copy_id=payload.inventory_copy_id)
    now = utc_now()
    row = MarketplaceListing(
        owner_id=owner_id,
        inventory_copy_id=payload.inventory_copy_id,
        listing_title=payload.listing_title.strip(),
        listing_description=(payload.listing_description or "").strip() or None,
        listing_type=payload.listing_type.strip(),
        condition_label=payload.condition_label.strip(),
        grade_label=(payload.grade_label or "").strip() or None,
        asking_price=payload.asking_price,
        currency=_normalize_currency(payload.currency),
        quantity=payload.quantity,
        status=LISTING_STATUS_DRAFT,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    _replace_variants(session, listing_id=int(row.id or 0), variants=payload.variants)
    _append_status_history(
        session,
        listing_id=int(row.id or 0),
        previous_status=None,
        new_status=row.status,
        reason="listing_created",
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def update_listing(session: Session, *, owner_id: int, listing_id: int, payload: MarketplaceListingUpdate) -> MarketplaceListingDetail:
    row = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    if row.status == LISTING_STATUS_ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived marketplace listings cannot be updated.")

    if "inventory_copy_id" in payload.model_fields_set:
        _ensure_inventory_access(session, owner_id=owner_id, inventory_copy_id=payload.inventory_copy_id)
        row.inventory_copy_id = payload.inventory_copy_id
    if "listing_title" in payload.model_fields_set and payload.listing_title is not None:
        row.listing_title = payload.listing_title.strip()
    if "listing_description" in payload.model_fields_set:
        row.listing_description = (payload.listing_description or "").strip() or None
    if "listing_type" in payload.model_fields_set and payload.listing_type is not None:
        row.listing_type = payload.listing_type.strip()
    if "condition_label" in payload.model_fields_set and payload.condition_label is not None:
        row.condition_label = payload.condition_label.strip()
    if "grade_label" in payload.model_fields_set:
        row.grade_label = (payload.grade_label or "").strip() or None
    if "asking_price" in payload.model_fields_set and payload.asking_price is not None:
        row.asking_price = payload.asking_price
    if "currency" in payload.model_fields_set and payload.currency is not None:
        row.currency = _normalize_currency(payload.currency)
    if "quantity" in payload.model_fields_set and payload.quantity is not None:
        row.quantity = payload.quantity
    row.updated_at = utc_now()
    session.add(row)
    if payload.variants is not None:
        _replace_variants(session, listing_id=listing_id, variants=payload.variants)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def get_listing(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceListingDetail:
    row = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    return _detail(session, row)


def list_listings(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceListingListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceListing)
        .where(MarketplaceListing.owner_id == owner_id)
        .order_by(MarketplaceListing.created_at.asc(), MarketplaceListing.id.asc())
    ).all()
    items = [_listing_read(row) for row in rows]
    return MarketplaceListingListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def archive_listing(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceListingDetail:
    row = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    previous_status = row.status
    if previous_status == LISTING_STATUS_ARCHIVED:
        return _detail(session, row)
    row.status = LISTING_STATUS_ARCHIVED
    row.updated_at = utc_now()
    session.add(row)
    _append_status_history(
        session,
        listing_id=listing_id,
        previous_status=previous_status,
        new_status=row.status,
        reason="listing_archived",
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def mark_ready_to_publish(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceListingDetail:
    row = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    previous_status = row.status
    if previous_status == LISTING_STATUS_ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived marketplace listings cannot be marked ready to publish.")
    if previous_status == LISTING_STATUS_READY_TO_PUBLISH:
        return _detail(session, row)
    row.status = LISTING_STATUS_READY_TO_PUBLISH
    row.updated_at = utc_now()
    session.add(row)
    _append_status_history(
        session,
        listing_id=listing_id,
        previous_status=previous_status,
        new_status=row.status,
        reason="ready_to_publish",
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)
