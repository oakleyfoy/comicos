from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace_sync import MarketplaceOrder
from app.schemas.marketplace_sync import MarketplaceOrderCreate, MarketplaceOrderItemCreate
from app.schemas.whatnot import WhatnotImportOrdersResponse
from app.services.marketplace_orders import create_order, get_order
from app.services.whatnot_accounts import get_owner_whatnot_account
from app.services.whatnot_connector import WhatnotConnector


def _existing_order(
    session: Session,
    *,
    owner_id: int,
    marketplace_account_id: int,
    external_order_id: str,
) -> MarketplaceOrder | None:
    return session.exec(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.owner_id == owner_id)
        .where(MarketplaceOrder.marketplace_account_id == marketplace_account_id)
        .where(MarketplaceOrder.external_order_id == external_order_id)
    ).first()


def map_external_order(session: Session, *, owner_id: int, external_order: dict) -> MarketplaceOrderCreate:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    items = [
        MarketplaceOrderItemCreate(
            listing_id=item.get("listing_id"),
            inventory_copy_id=item.get("inventory_copy_id"),
            external_item_id=str(item.get("external_item_id") or ""),
            title=str(item.get("title") or "Whatnot Item"),
            quantity=int(item.get("quantity") or 1),
            unit_price=Decimal(str(item.get("unit_price") or "0.00")),
        )
        for item in external_order.get("items") or []
    ]
    if not items:
        raise HTTPException(status_code=422, detail="Whatnot order import requires at least one item.")
    return MarketplaceOrderCreate(
        marketplace_id=account.marketplace_id,
        marketplace_account_id=account.id,
        external_order_id=str(external_order["external_order_id"]),
        buyer_name=str(external_order.get("buyer_name") or ""),
        buyer_email=str(external_order.get("buyer_email") or ""),
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        currency=str(external_order.get("currency") or "USD"),
        items=items,
    )


def create_internal_order(session: Session, *, owner_id: int, payload: MarketplaceOrderCreate):
    return create_order(session, owner_id=owner_id, payload=payload)


def import_order_items(session: Session, *, owner_id: int, external_order: dict):
    payload = map_external_order(session, owner_id=owner_id, external_order=external_order)
    return create_internal_order(session, owner_id=owner_id, payload=payload)


def import_orders(session: Session, *, owner_id: int) -> WhatnotImportOrdersResponse:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    external_orders = connector.import_orders(session)
    imported_ids: list[int] = []
    skipped = 0
    for external_order in external_orders:
        external_id = str(external_order["external_order_id"])
        if _existing_order(
            session,
            owner_id=owner_id,
            marketplace_account_id=account.id,
            external_order_id=external_id,
        ):
            skipped += 1
            continue
        detail = import_order_items(session, owner_id=owner_id, external_order=external_order)
        imported_ids.append(detail.order.id)
    return WhatnotImportOrdersResponse(
        imported_count=len(imported_ids),
        skipped_duplicates=skipped,
        order_ids=imported_ids,
    )
