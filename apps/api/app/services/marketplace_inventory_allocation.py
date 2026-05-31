from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace_sync import MarketplaceOrder, MarketplaceOrderItem
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate
from app.services.marketplace_inventory_reservations import (
    RESERVATION_STATUS_ACTIVE,
    create_reservation,
    release_reservation,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def allocate_order_inventory(session: Session, *, owner_id: int, order_id: int) -> None:
    order = session.get(MarketplaceOrder, order_id)
    if order is None or order.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    items = session.exec(
        select(MarketplaceOrderItem)
        .where(MarketplaceOrderItem.order_id == order_id)
        .order_by(MarketplaceOrderItem.created_at.asc(), MarketplaceOrderItem.id.asc())
    ).all()
    for item in items:
        if item.item_status != "PENDING":
            continue
        if item.listing_id is None:
            continue
        create_reservation(
            session,
            owner_id=owner_id,
            payload=MarketplaceInventoryReservationCreate(
                listing_id=item.listing_id,
                inventory_copy_id=item.inventory_copy_id,
                reservation_type="ORDER_ALLOCATION",
                quantity_reserved=item.quantity,
                source=f"order_item:{int(item.id or 0)}",
                expires_at=None,
            ),
        )
        item.item_status = "ALLOCATED"
        item.updated_at = utc_now()
        session.add(item)
    session.commit()


def release_order_inventory(session: Session, *, owner_id: int, order_id: int) -> None:
    order = session.get(MarketplaceOrder, order_id)
    if order is None or order.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    from app.models.marketplace_sync import MarketplaceInventoryReservation

    items = session.exec(
        select(MarketplaceOrderItem)
        .where(MarketplaceOrderItem.order_id == order_id)
        .order_by(MarketplaceOrderItem.created_at.asc(), MarketplaceOrderItem.id.asc())
    ).all()
    for item in items:
        reservations = session.exec(
            select(MarketplaceInventoryReservation)
            .where(MarketplaceInventoryReservation.owner_id == owner_id)
            .where(MarketplaceInventoryReservation.source == f"order_item:{int(item.id or 0)}")
        ).all()
        for reservation in reservations:
            if reservation.status == RESERVATION_STATUS_ACTIVE:
                release_reservation(session, owner_id=owner_id, reservation_id=int(reservation.id or 0))
        if item.item_status not in {"SOLD"}:
            item.item_status = "RELEASED"
            item.updated_at = utc_now()
            session.add(item)
    session.commit()


def mark_items_sold(session: Session, *, owner_id: int, order_id: int) -> None:
    order = session.get(MarketplaceOrder, order_id)
    if order is None or order.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    items = session.exec(
        select(MarketplaceOrderItem)
        .where(MarketplaceOrderItem.order_id == order_id)
        .order_by(MarketplaceOrderItem.created_at.asc(), MarketplaceOrderItem.id.asc())
    ).all()
    for item in items:
        item.item_status = "SOLD"
        item.updated_at = utc_now()
        session.add(item)
    session.commit()
    release_order_inventory(session, owner_id=owner_id, order_id=order_id)
