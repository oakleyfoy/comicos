from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.marketplace_listing import MarketplaceListing
from app.models.marketplace_sync import (
    MarketplaceInventoryAvailability,
    MarketplaceInventoryReservation,
    MarketplaceOrderItem,
)
from app.schemas.marketplace_sync import (
    MarketplaceInventoryAvailabilityListResponse,
    MarketplaceInventoryAvailabilityRead,
)
from app.services.marketplace_listings import _clamp, _owner_listing_or_404

ACTIVE_RESERVATION_STATUSES = {"ACTIVE"}
SOLD_ITEM_STATUSES = {"SOLD"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _availability_read(row: MarketplaceInventoryAvailability) -> MarketplaceInventoryAvailabilityRead:
    return MarketplaceInventoryAvailabilityRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        listing_id=row.listing_id,
        inventory_copy_id=row.inventory_copy_id,
        total_quantity=row.total_quantity,
        reserved_quantity=row.reserved_quantity,
        available_quantity=row.available_quantity,
        sold_quantity=row.sold_quantity,
        calculated_at=row.calculated_at,
    )


def calculate_availability(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceInventoryAvailabilityRead:
    listing = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    reserved_quantity = sum(
        row.quantity_reserved
        for row in session.exec(
            select(MarketplaceInventoryReservation)
            .where(MarketplaceInventoryReservation.owner_id == owner_id)
            .where(MarketplaceInventoryReservation.listing_id == listing_id)
        ).all()
        if row.status in ACTIVE_RESERVATION_STATUSES
    )
    sold_quantity = sum(
        row.quantity
        for row in session.exec(
            select(MarketplaceOrderItem)
            .where(MarketplaceOrderItem.listing_id == listing_id)
        ).all()
        if row.item_status in SOLD_ITEM_STATUSES
    )
    available_quantity = max(listing.quantity - reserved_quantity - sold_quantity, 0)
    row = MarketplaceInventoryAvailability(
        owner_id=owner_id,
        listing_id=listing_id,
        inventory_copy_id=listing.inventory_copy_id,
        total_quantity=listing.quantity,
        reserved_quantity=reserved_quantity,
        available_quantity=available_quantity,
        sold_quantity=sold_quantity,
        calculated_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _availability_read(row)


def recalculate_listing_availability(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceInventoryAvailabilityRead:
    return calculate_availability(session, owner_id=owner_id, listing_id=listing_id)


def get_availability(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceInventoryAvailabilityRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = session.exec(
        select(MarketplaceInventoryAvailability)
        .where(MarketplaceInventoryAvailability.owner_id == owner_id)
        .where(MarketplaceInventoryAvailability.listing_id == listing_id)
        .order_by(MarketplaceInventoryAvailability.calculated_at.desc(), MarketplaceInventoryAvailability.id.desc())
    ).first()
    if row is None:
        return calculate_availability(session, owner_id=owner_id, listing_id=listing_id)
    return _availability_read(row)


def list_availability(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceInventoryAvailabilityListResponse:
    limit, offset = _clamp(limit, offset)
    listings = session.exec(
        select(MarketplaceListing)
        .where(MarketplaceListing.owner_id == owner_id)
        .order_by(MarketplaceListing.created_at.asc(), MarketplaceListing.id.asc())
    ).all()
    items = [get_availability(session, owner_id=owner_id, listing_id=int(listing.id or 0)) for listing in listings]
    return MarketplaceInventoryAvailabilityListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )
