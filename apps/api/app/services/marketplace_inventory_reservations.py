from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace_sync import MarketplaceInventoryReservation
from app.schemas.marketplace_sync import (
    MarketplaceInventoryReservationCreate,
    MarketplaceInventoryReservationListResponse,
    MarketplaceInventoryReservationRead,
)
from app.services.marketplace_inventory_availability import get_availability, recalculate_listing_availability
from app.services.marketplace_listings import _clamp, _owner_listing_or_404

RESERVATION_STATUS_ACTIVE = "ACTIVE"
RESERVATION_STATUS_RELEASED = "RELEASED"
RESERVATION_STATUS_EXPIRED = "EXPIRED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reservation_read(row: MarketplaceInventoryReservation) -> MarketplaceInventoryReservationRead:
    return MarketplaceInventoryReservationRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        listing_id=row.listing_id,
        inventory_copy_id=row.inventory_copy_id,
        reservation_uuid=row.reservation_uuid,
        reservation_type=row.reservation_type,
        quantity_reserved=row.quantity_reserved,
        status=row.status,
        source=row.source,
        expires_at=row.expires_at,
        created_at=row.created_at,
        released_at=row.released_at,
    )


def _reservation_or_404(session: Session, *, reservation_id: int) -> MarketplaceInventoryReservation:
    row = session.get(MarketplaceInventoryReservation, reservation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace inventory reservation not found.")
    return row


def _owner_reservation_or_404(session: Session, *, owner_id: int, reservation_id: int) -> MarketplaceInventoryReservation:
    row = _reservation_or_404(session, reservation_id=reservation_id)
    if row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace inventory reservation not found.")
    return row


def create_reservation(
    session: Session,
    *,
    owner_id: int,
    payload: MarketplaceInventoryReservationCreate,
) -> MarketplaceInventoryReservationRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=payload.listing_id)
    availability = get_availability(session, owner_id=owner_id, listing_id=payload.listing_id)
    if payload.quantity_reserved > availability.available_quantity:
        raise HTTPException(status_code=409, detail="Cannot reserve more than the available quantity.")
    row = MarketplaceInventoryReservation(
        owner_id=owner_id,
        listing_id=payload.listing_id,
        inventory_copy_id=payload.inventory_copy_id,
        reservation_type=payload.reservation_type.strip().upper(),
        quantity_reserved=payload.quantity_reserved,
        status=RESERVATION_STATUS_ACTIVE,
        source=payload.source.strip(),
        expires_at=payload.expires_at,
        created_at=utc_now(),
        released_at=None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    recalculate_listing_availability(session, owner_id=owner_id, listing_id=payload.listing_id)
    return _reservation_read(row)


def release_reservation(session: Session, *, owner_id: int, reservation_id: int) -> MarketplaceInventoryReservationRead:
    row = _owner_reservation_or_404(session, owner_id=owner_id, reservation_id=reservation_id)
    if row.status == RESERVATION_STATUS_RELEASED:
        return _reservation_read(row)
    row.status = RESERVATION_STATUS_RELEASED
    row.released_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    recalculate_listing_availability(session, owner_id=owner_id, listing_id=row.listing_id)
    return _reservation_read(row)


def expire_reservations(session: Session, *, owner_id: int) -> list[MarketplaceInventoryReservationRead]:
    now = utc_now()
    rows = session.exec(
        select(MarketplaceInventoryReservation)
        .where(MarketplaceInventoryReservation.owner_id == owner_id)
        .where(MarketplaceInventoryReservation.status == RESERVATION_STATUS_ACTIVE)
    ).all()
    expired: list[MarketplaceInventoryReservationRead] = []
    affected_listing_ids: set[int] = set()
    for row in rows:
        expires_at = _as_utc(row.expires_at) if row.expires_at is not None else None
        if expires_at is None or expires_at > now:
            continue
        row.status = RESERVATION_STATUS_EXPIRED
        row.released_at = now
        session.add(row)
        affected_listing_ids.add(row.listing_id)
        expired.append(_reservation_read(row))
    session.commit()
    for listing_id in sorted(affected_listing_ids):
        recalculate_listing_availability(session, owner_id=owner_id, listing_id=listing_id)
    return expired


def list_reservations(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceInventoryReservationListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceInventoryReservation)
        .where(MarketplaceInventoryReservation.owner_id == owner_id)
        .order_by(MarketplaceInventoryReservation.created_at.asc(), MarketplaceInventoryReservation.id.asc())
    ).all()
    items = [_reservation_read(row) for row in rows]
    return MarketplaceInventoryReservationListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_reservation(session: Session, *, owner_id: int, reservation_id: int) -> MarketplaceInventoryReservationRead:
    row = _owner_reservation_or_404(session, owner_id=owner_id, reservation_id=reservation_id)
    return _reservation_read(row)
