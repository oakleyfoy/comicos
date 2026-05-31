from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount as MarketplaceConnectorAccount
from app.models.marketplace import MarketplaceDefinition as MarketplaceConnectorDefinition
from app.models.marketplace_sync import MarketplaceOrder, MarketplaceOrderEvent, MarketplaceOrderItem
from app.schemas.marketplace_sync import (
    MarketplaceOrderCreate,
    MarketplaceOrderDetail,
    MarketplaceOrderEventRead,
    MarketplaceOrderItemCreate,
    MarketplaceOrderItemRead,
    MarketplaceOrderListResponse,
    MarketplaceOrderRead,
)
from app.services.marketplace_inventory_allocation import allocate_order_inventory, mark_items_sold, release_order_inventory
from app.services.marketplace_inventory_availability import get_availability
from app.services.marketplace_listings import _clamp

ORDER_STATUS_PENDING = "PENDING"
ORDER_STATUS_PAID = "PAID"
ORDER_STATUS_FULFILLED = "FULFILLED"
ORDER_STATUS_CANCELLED = "CANCELLED"

ALLOWED_ORDER_TRANSITIONS: dict[str, set[str]] = {
    ORDER_STATUS_PENDING: {ORDER_STATUS_PAID, ORDER_STATUS_CANCELLED},
    ORDER_STATUS_PAID: {ORDER_STATUS_FULFILLED, ORDER_STATUS_CANCELLED},
    ORDER_STATUS_FULFILLED: set(),
    ORDER_STATUS_CANCELLED: set(),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _order_read(row: MarketplaceOrder) -> MarketplaceOrderRead:
    return MarketplaceOrderRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        marketplace_id=row.marketplace_id,
        marketplace_account_id=row.marketplace_account_id,
        order_uuid=row.order_uuid,
        external_order_id=row.external_order_id,
        order_status=row.order_status,
        buyer_name=row.buyer_name,
        buyer_email=row.buyer_email,
        subtotal_amount=row.subtotal_amount,
        shipping_amount=row.shipping_amount,
        tax_amount=row.tax_amount,
        total_amount=row.total_amount,
        currency=row.currency,
        ordered_at=row.ordered_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _item_read(row: MarketplaceOrderItem) -> MarketplaceOrderItemRead:
    return MarketplaceOrderItemRead(
        id=int(row.id or 0),
        order_id=row.order_id,
        listing_id=row.listing_id,
        inventory_copy_id=row.inventory_copy_id,
        external_item_id=row.external_item_id,
        title=row.title,
        quantity=row.quantity,
        unit_price=row.unit_price,
        total_price=row.total_price,
        item_status=row.item_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event_read(row: MarketplaceOrderEvent) -> MarketplaceOrderEventRead:
    return MarketplaceOrderEventRead(
        id=int(row.id or 0),
        order_id=row.order_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _order_or_404(session: Session, *, order_id: int) -> MarketplaceOrder:
    row = session.get(MarketplaceOrder, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    return row


def _owner_order_or_404(session: Session, *, owner_id: int, order_id: int) -> MarketplaceOrder:
    row = _order_or_404(session, order_id=order_id)
    if row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    return row


def _append_event(session: Session, *, order_id: int, event_type: str, event_payload_json: dict) -> None:
    session.add(
        MarketplaceOrderEvent(
            order_id=order_id,
            event_type=event_type,
            event_payload_json=event_payload_json,
            created_at=utc_now(),
        )
    )


def _items(session: Session, *, order_id: int) -> list[MarketplaceOrderItemRead]:
    rows = session.exec(
        select(MarketplaceOrderItem)
        .where(MarketplaceOrderItem.order_id == order_id)
        .order_by(MarketplaceOrderItem.created_at.asc(), MarketplaceOrderItem.id.asc())
    ).all()
    return [_item_read(row) for row in rows]


def _events(session: Session, *, order_id: int) -> list[MarketplaceOrderEventRead]:
    rows = session.exec(
        select(MarketplaceOrderEvent)
        .where(MarketplaceOrderEvent.order_id == order_id)
        .order_by(MarketplaceOrderEvent.created_at.asc(), MarketplaceOrderEvent.id.asc())
    ).all()
    return [_event_read(row) for row in rows]


def _detail(session: Session, row: MarketplaceOrder) -> MarketplaceOrderDetail:
    order_id = int(row.id or 0)
    return MarketplaceOrderDetail(
        order=_order_read(row),
        items=_items(session, order_id=order_id),
        events=_events(session, order_id=order_id),
    )


def _validate_marketplace_refs(
    session: Session,
    *,
    owner_id: int,
    marketplace_id: int | None,
    marketplace_account_id: int | None,
) -> None:
    if marketplace_id is not None and session.get(MarketplaceConnectorDefinition, marketplace_id) is None:
        raise HTTPException(status_code=404, detail="Marketplace definition not found.")
    if marketplace_account_id is not None:
        account = session.get(MarketplaceConnectorAccount, marketplace_account_id)
        if account is None or account.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Marketplace account not found.")
        if marketplace_id is not None and account.marketplace_id != marketplace_id:
            raise HTTPException(status_code=422, detail="Marketplace account does not match the marketplace.")


def _subtotal(items: list[MarketplaceOrderItemCreate]) -> Decimal:
    return sum((item.unit_price * item.quantity for item in items), Decimal("0"))


def _validate_item_availability(session: Session, *, owner_id: int, items: list[MarketplaceOrderItemCreate]) -> None:
    quantities_by_listing: dict[int, int] = {}
    for item in items:
        if item.listing_id is None:
            continue
        quantities_by_listing[item.listing_id] = quantities_by_listing.get(item.listing_id, 0) + item.quantity
    for listing_id, requested_quantity in quantities_by_listing.items():
        availability = get_availability(session, owner_id=owner_id, listing_id=listing_id)
        if requested_quantity > availability.available_quantity:
            raise HTTPException(status_code=409, detail="Order quantity exceeds available marketplace listing quantity.")


def create_order(session: Session, *, owner_id: int, payload: MarketplaceOrderCreate) -> MarketplaceOrderDetail:
    _validate_marketplace_refs(
        session,
        owner_id=owner_id,
        marketplace_id=payload.marketplace_id,
        marketplace_account_id=payload.marketplace_account_id,
    )
    _validate_item_availability(session, owner_id=owner_id, items=payload.items)
    subtotal_amount = _subtotal(payload.items)
    total_amount = subtotal_amount + payload.shipping_amount + payload.tax_amount
    now = utc_now()
    row = MarketplaceOrder(
        owner_id=owner_id,
        marketplace_id=payload.marketplace_id,
        marketplace_account_id=payload.marketplace_account_id,
        external_order_id=(payload.external_order_id or "").strip() or None,
        order_status=ORDER_STATUS_PENDING,
        buyer_name=(payload.buyer_name or "").strip() or None,
        buyer_email=(payload.buyer_email or "").strip() or None,
        subtotal_amount=subtotal_amount,
        shipping_amount=payload.shipping_amount,
        tax_amount=payload.tax_amount,
        total_amount=total_amount,
        currency=payload.currency.strip().upper(),
        ordered_at=payload.ordered_at,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    for item in payload.items:
        session.add(
            MarketplaceOrderItem(
                order_id=int(row.id or 0),
                listing_id=item.listing_id,
                inventory_copy_id=item.inventory_copy_id,
                external_item_id=(item.external_item_id or "").strip() or None,
                title=item.title.strip(),
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.unit_price * item.quantity,
                item_status="PENDING",
                created_at=now,
                updated_at=now,
            )
        )
    _append_event(
        session,
        order_id=int(row.id or 0),
        event_type="marketplace_order_created",
        event_payload_json={"item_count": len(payload.items), "order_status": ORDER_STATUS_PENDING},
    )
    session.commit()
    allocate_order_inventory(session, owner_id=owner_id, order_id=int(row.id or 0))
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=int(row.id or 0))
    return _detail(session, row)


def add_order_item(session: Session, *, owner_id: int, order_id: int, payload: MarketplaceOrderItemCreate) -> MarketplaceOrderDetail:
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    _validate_item_availability(session, owner_id=owner_id, items=[payload])
    now = utc_now()
    item = MarketplaceOrderItem(
        order_id=order_id,
        listing_id=payload.listing_id,
        inventory_copy_id=payload.inventory_copy_id,
        external_item_id=(payload.external_item_id or "").strip() or None,
        title=payload.title.strip(),
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_price=payload.unit_price * payload.quantity,
        item_status="PENDING",
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    row.subtotal_amount = row.subtotal_amount + item.total_price
    row.total_amount = row.subtotal_amount + row.shipping_amount + row.tax_amount
    row.updated_at = now
    session.add(row)
    _append_event(session, order_id=order_id, event_type="marketplace_order_item_added", event_payload_json={"title": item.title})
    session.commit()
    allocate_order_inventory(session, owner_id=owner_id, order_id=order_id)
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    return _detail(session, row)


def update_order_status(session: Session, *, owner_id: int, order_id: int, new_status: str, event_type: str) -> MarketplaceOrderDetail:
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    previous_status = row.order_status
    if previous_status == new_status:
        return _detail(session, row)
    if new_status not in ALLOWED_ORDER_TRANSITIONS.get(previous_status, set()):
        raise HTTPException(status_code=409, detail="Marketplace order status transition is not allowed.")
    row.order_status = new_status
    row.updated_at = utc_now()
    session.add(row)
    _append_event(
        session,
        order_id=order_id,
        event_type=event_type,
        event_payload_json={"previous_status": previous_status, "new_status": new_status},
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def cancel_order(session: Session, *, owner_id: int, order_id: int) -> MarketplaceOrderDetail:
    detail = update_order_status(
        session,
        owner_id=owner_id,
        order_id=order_id,
        new_status=ORDER_STATUS_CANCELLED,
        event_type="marketplace_order_cancelled",
    )
    release_order_inventory(session, owner_id=owner_id, order_id=order_id)
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    return _detail(session, row)


def mark_order_paid(session: Session, *, owner_id: int, order_id: int) -> MarketplaceOrderDetail:
    return update_order_status(
        session,
        owner_id=owner_id,
        order_id=order_id,
        new_status=ORDER_STATUS_PAID,
        event_type="marketplace_order_paid",
    )


def mark_order_fulfilled(session: Session, *, owner_id: int, order_id: int) -> MarketplaceOrderDetail:
    detail = update_order_status(
        session,
        owner_id=owner_id,
        order_id=order_id,
        new_status=ORDER_STATUS_FULFILLED,
        event_type="marketplace_order_fulfilled",
    )
    mark_items_sold(session, owner_id=owner_id, order_id=order_id)
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    return _detail(session, row)


def list_orders(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceOrderListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.owner_id == owner_id)
        .order_by(MarketplaceOrder.created_at.asc(), MarketplaceOrder.id.asc())
    ).all()
    items = [_order_read(row) for row in rows]
    return MarketplaceOrderListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_order(session: Session, *, owner_id: int, order_id: int) -> MarketplaceOrderDetail:
    row = _owner_order_or_404(session, owner_id=owner_id, order_id=order_id)
    return _detail(session, row)
