from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    MarketplaceOrder,
    MarketplaceOrderLineItem,
    MarketplaceTransaction,
)
from app.schemas.marketplace_orders import (
    MarketplaceOrderImportRequest,
    MarketplaceOrderImportSummaryResponse,
    MarketplaceOrderLineItemImportRequest,
    MarketplaceTransactionImportRequest,
)
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.organization_inventory_access import validate_org_inventory_membership

ORDER_STATUS_IMPORTED = "imported"
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUSES = {
    ORDER_STATUS_IMPORTED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_CANCELLED,
}

TRANSACTION_STATUS_PENDING = "pending"
TRANSACTION_STATUS_COMPLETED = "completed"
TRANSACTION_STATUS_FAILED = "failed"
TRANSACTION_STATUSES = {
    TRANSACTION_STATUS_PENDING,
    TRANSACTION_STATUS_COMPLETED,
    TRANSACTION_STATUS_FAILED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class OrderImportResult:
    order: MarketplaceOrder
    line_items: tuple[MarketplaceOrderLineItem, ...]
    transactions: tuple[MarketplaceTransaction, ...]
    duplicate_detected: bool


def validate_order_payload(
    session: Session,
    *,
    organization_id: int,
    payload: MarketplaceOrderImportRequest,
) -> MarketplaceAccount:
    order_status = payload.order_status.strip().lower()
    if order_status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported marketplace order status.")

    account = session.get(MarketplaceAccount, payload.marketplace_account_id)
    if account is None or account.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    if account.account_status != ACCOUNT_STATUS_CONNECTED:
        raise HTTPException(status_code=409, detail="Marketplace account must be connected for order imports.")

    marketplace_type = (payload.marketplace_type or account.marketplace_type).strip().lower()
    if marketplace_type != account.marketplace_type:
        raise HTTPException(status_code=422, detail="Marketplace type must match the connected marketplace account.")

    order_currency = payload.order_currency.strip().upper()
    if len(order_currency) < 3:
        raise HTTPException(status_code=422, detail="Order currency is required.")

    seen_listing_identifiers: set[str] = set()
    for item in payload.line_items:
        listing_identifier = item.marketplace_listing_identifier.strip()
        if not listing_identifier:
            raise HTTPException(status_code=422, detail="Marketplace listing identifier is required for each line item.")
        if listing_identifier in seen_listing_identifiers:
            raise HTTPException(status_code=422, detail="Marketplace listing identifiers must be unique per order import.")
        seen_listing_identifiers.add(listing_identifier)
        if _normalize_decimal(item.unit_price * item.quantity) != _normalize_decimal(item.line_total):
            raise HTTPException(status_code=422, detail="Line item totals must equal quantity multiplied by unit price.")
        if item.inventory_item_id is not None:
            validate_org_inventory_membership(
                session,
                organization_id=organization_id,
                inventory_item_id=item.inventory_item_id,
            )

    seen_transaction_references: set[str] = set()
    for transaction in payload.transactions:
        status = transaction.transaction_status.strip().lower()
        if status not in TRANSACTION_STATUSES:
            raise HTTPException(status_code=422, detail="Unsupported marketplace transaction status.")
        reference = transaction.transaction_reference.strip()
        if reference in seen_transaction_references:
            raise HTTPException(status_code=422, detail="Transaction references must be unique within an import payload.")
        seen_transaction_references.add(reference)
        if _normalize_decimal(transaction.gross_amount - transaction.fee_amount) != _normalize_decimal(transaction.net_amount):
            raise HTTPException(status_code=422, detail="Transaction net amount must equal gross amount minus fee amount.")
        if transaction.transaction_currency.strip().upper() != order_currency:
            raise HTTPException(status_code=422, detail="Transaction currencies must match the order currency.")

    return account


def detect_duplicate_order(
    session: Session,
    *,
    marketplace_account_id: int,
    marketplace_order_identifier: str,
) -> MarketplaceOrder | None:
    query = (
        select(MarketplaceOrder)
        .where(MarketplaceOrder.marketplace_account_id == marketplace_account_id)
        .where(MarketplaceOrder.marketplace_order_identifier == marketplace_order_identifier.strip())
        .order_by(MarketplaceOrder.id.asc())
    )
    return session.exec(query).first()


def register_order_line_items(
    session: Session,
    *,
    order: MarketplaceOrder,
    line_items: list[MarketplaceOrderLineItemImportRequest],
) -> tuple[MarketplaceOrderLineItem, ...]:
    created: list[MarketplaceOrderLineItem] = []
    now = utc_now()
    for item in sorted(line_items, key=lambda row: (row.marketplace_listing_identifier, row.inventory_item_id or 0)):
        row = MarketplaceOrderLineItem(
            marketplace_order_id=int(order.id or 0),
            inventory_item_id=item.inventory_item_id,
            marketplace_listing_identifier=item.marketplace_listing_identifier.strip(),
            quantity=item.quantity,
            unit_price=_normalize_decimal(item.unit_price),
            line_total=_normalize_decimal(item.line_total),
            created_at=now,
        )
        session.add(row)
        session.flush()
        created.append(row)
    return tuple(created)


def ingest_marketplace_transaction(
    session: Session,
    *,
    order: MarketplaceOrder,
    payload: MarketplaceTransactionImportRequest,
) -> tuple[MarketplaceTransaction, bool]:
    reference = payload.transaction_reference.strip()
    existing = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.marketplace_order_id == int(order.id or 0))
        .where(MarketplaceTransaction.transaction_reference == reference)
        .order_by(MarketplaceTransaction.id.asc())
    ).first()
    if existing is not None:
        return existing, False

    row = MarketplaceTransaction(
        organization_id=order.organization_id,
        marketplace_order_id=int(order.id or 0),
        transaction_type=payload.transaction_type.strip().lower(),
        transaction_status=payload.transaction_status.strip().lower(),
        gross_amount=_normalize_decimal(payload.gross_amount),
        fee_amount=_normalize_decimal(payload.fee_amount),
        net_amount=_normalize_decimal(payload.net_amount),
        transaction_currency=payload.transaction_currency.strip().upper(),
        transaction_reference=reference,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row, True


def ingest_marketplace_order(
    session: Session,
    *,
    organization_id: int,
    payload: MarketplaceOrderImportRequest,
) -> OrderImportResult:
    account = validate_order_payload(session, organization_id=organization_id, payload=payload)
    existing = detect_duplicate_order(
        session,
        marketplace_account_id=int(account.id or 0),
        marketplace_order_identifier=payload.marketplace_order_identifier,
    )
    if existing is not None:
        existing.order_status = payload.order_status.strip().lower()
        existing.buyer_identifier = payload.buyer_identifier or None
        existing.order_total = _normalize_decimal(payload.order_total)
        existing.order_currency = payload.order_currency.strip().upper()
        existing.ordered_at = payload.ordered_at or existing.ordered_at
        existing.imported_at = utc_now()
        session.add(existing)
        session.flush()
        line_items = session.exec(
            select(MarketplaceOrderLineItem)
            .where(MarketplaceOrderLineItem.marketplace_order_id == int(existing.id or 0))
            .order_by(MarketplaceOrderLineItem.created_at.asc(), MarketplaceOrderLineItem.id.asc())
        ).all()
        existing_transactions = session.exec(
            select(MarketplaceTransaction)
            .where(MarketplaceTransaction.marketplace_order_id == int(existing.id or 0))
            .order_by(MarketplaceTransaction.created_at.asc(), MarketplaceTransaction.id.asc())
        ).all()
        transactions_by_reference = {row.transaction_reference: row for row in existing_transactions}
        for transaction in sorted(
            payload.transactions,
            key=lambda row: (row.transaction_reference, row.transaction_type, row.transaction_status),
        ):
            if transaction.transaction_reference.strip() in transactions_by_reference:
                continue
            tx, _created = ingest_marketplace_transaction(session, order=existing, payload=transaction)
            transactions_by_reference[tx.transaction_reference] = tx
        transactions = sorted(
            transactions_by_reference.values(),
            key=lambda row: (row.created_at, row.id or 0),
        )
        return OrderImportResult(
            order=existing,
            line_items=tuple(line_items),
            transactions=tuple(transactions),
            duplicate_detected=True,
        )

    now = utc_now()
    order = MarketplaceOrder(
        organization_id=organization_id,
        marketplace_account_id=int(account.id or 0),
        marketplace_order_identifier=payload.marketplace_order_identifier.strip(),
        marketplace_type=account.marketplace_type,
        order_status=payload.order_status.strip().lower(),
        buyer_identifier=(payload.buyer_identifier or None),
        order_total=_normalize_decimal(payload.order_total),
        order_currency=payload.order_currency.strip().upper(),
        ordered_at=payload.ordered_at or now,
        imported_at=now,
        created_at=now,
    )
    session.add(order)
    session.flush()

    line_items = register_order_line_items(session, order=order, line_items=payload.line_items)
    created_transactions: list[MarketplaceTransaction] = []
    for transaction in sorted(
        payload.transactions,
        key=lambda row: (row.transaction_reference, row.transaction_type, row.transaction_status),
    ):
        tx, _created = ingest_marketplace_transaction(session, order=order, payload=transaction)
        created_transactions.append(tx)

    return OrderImportResult(
        order=order,
        line_items=line_items,
        transactions=tuple(created_transactions),
        duplicate_detected=False,
    )


def generate_order_import_summary(result: OrderImportResult) -> MarketplaceOrderImportSummaryResponse:
    return MarketplaceOrderImportSummaryResponse(
        order_id=int(result.order.id or 0),
        duplicate_detected=result.duplicate_detected,
        imported_line_items=len(result.line_items),
        imported_transactions=len(result.transactions),
        order_total=result.order.order_total,
        order_currency=result.order.order_currency,
    )
