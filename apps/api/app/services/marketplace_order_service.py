from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    MarketplaceOrder,
    MarketplaceOrderEvent,
    MarketplaceOrderLineItem,
    MarketplaceTransaction,
)
from app.schemas.marketplace_orders import (
    MarketplaceOrderDetailResponse,
    MarketplaceOrderEventResponse,
    MarketplaceOrderImportRequest,
    MarketplaceOrderImportSummaryResponse,
    MarketplaceOrderLineItemResponse,
    MarketplaceOrderListResponse,
    MarketplaceOrderPermissionResponse,
    MarketplaceOrderReconcileRequest,
    MarketplaceOrderResponse,
    MarketplaceTransactionListResponse,
    MarketplaceTransactionReconciliationReportResponse,
    MarketplaceTransactionResponse,
)
from app.services.marketplace_order_ingestion import (
    OrderImportResult,
    detect_duplicate_order,
    generate_order_import_summary,
    ingest_marketplace_order,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
)
from app.services.marketplace_transaction_reconciliation import generate_transaction_report


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceOrderPermissionResponse:
    return MarketplaceOrderPermissionResponse(
        can_view=resolution.can_view,
        can_manage=resolution.can_manage,
    )


def _to_order_response(row: MarketplaceOrder) -> MarketplaceOrderResponse:
    return MarketplaceOrderResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_order_identifier=row.marketplace_order_identifier,
        marketplace_type=row.marketplace_type,
        order_status=row.order_status,
        buyer_identifier=row.buyer_identifier,
        order_total=row.order_total,
        order_currency=row.order_currency,
        ordered_at=row.ordered_at,
        imported_at=row.imported_at,
        created_at=row.created_at,
    )


def _to_line_item_response(row: MarketplaceOrderLineItem) -> MarketplaceOrderLineItemResponse:
    return MarketplaceOrderLineItemResponse(
        id=int(row.id or 0),
        marketplace_order_id=row.marketplace_order_id,
        inventory_item_id=row.inventory_item_id,
        marketplace_listing_identifier=row.marketplace_listing_identifier,
        quantity=row.quantity,
        unit_price=row.unit_price,
        line_total=row.line_total,
        created_at=row.created_at,
    )


def _to_transaction_response(row: MarketplaceTransaction) -> MarketplaceTransactionResponse:
    return MarketplaceTransactionResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_order_id=row.marketplace_order_id,
        transaction_type=row.transaction_type,
        transaction_status=row.transaction_status,
        gross_amount=row.gross_amount,
        fee_amount=row.fee_amount,
        net_amount=row.net_amount,
        transaction_currency=row.transaction_currency,
        transaction_reference=row.transaction_reference,
        created_at=row.created_at,
    )


def _to_event_response(row: MarketplaceOrderEvent) -> MarketplaceOrderEventResponse:
    return MarketplaceOrderEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_order_id=row.marketplace_order_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None or account.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return account


def _order_or_404(session: Session, *, organization_id: int, order_id: int) -> MarketplaceOrder:
    order = session.get(MarketplaceOrder, order_id)
    if order is None or order.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace order not found.")
    return order


def create_order_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_order_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceOrderEvent:
    row = MarketplaceOrderEvent(
        organization_id=organization_id,
        marketplace_order_id=marketplace_order_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _validate_order_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_order_id: int | None = None,
    action: str = "marketplace_order:view",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    if not resolution.can_view:
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=marketplace_order_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_order_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace order visibility is denied for this organization.")
    return resolution


def _validate_order_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None = None,
    action: str = "marketplace_order:manage",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    if not resolution.can_manage:
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_order_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason, "marketplace_account_id": marketplace_account_id},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace order management is denied for this organization.")
    if marketplace_account_id is not None:
        _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    return resolution


def _load_line_items(session: Session, *, order_id: int) -> list[MarketplaceOrderLineItem]:
    rows = session.exec(
        select(MarketplaceOrderLineItem)
        .where(MarketplaceOrderLineItem.marketplace_order_id == order_id)
        .order_by(MarketplaceOrderLineItem.created_at.asc(), MarketplaceOrderLineItem.id.asc())
    ).all()
    return list(rows)


def _load_transactions(session: Session, *, order_id: int) -> list[MarketplaceTransaction]:
    rows = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.marketplace_order_id == order_id)
        .order_by(MarketplaceTransaction.created_at.asc(), MarketplaceTransaction.id.asc())
    ).all()
    return list(rows)


def _load_events(session: Session, *, order_id: int) -> list[MarketplaceOrderEvent]:
    rows = session.exec(
        select(MarketplaceOrderEvent)
        .where(MarketplaceOrderEvent.marketplace_order_id == order_id)
        .order_by(MarketplaceOrderEvent.created_at.asc(), MarketplaceOrderEvent.id.asc())
    ).all()
    return list(rows)


def _detail_response(
    *,
    resolution: MarketplacePermissionResolution,
    result: OrderImportResult,
    events: list[MarketplaceOrderEvent],
) -> MarketplaceOrderDetailResponse:
    return MarketplaceOrderDetailResponse(
        order=_to_order_response(result.order),
        line_items=[_to_line_item_response(row) for row in result.line_items],
        transactions=[_to_transaction_response(row) for row in result.transactions],
        events=[_to_event_response(row) for row in events],
        import_summary=generate_order_import_summary(result),
        permissions=_permission_response(resolution),
    )


def create_order_import(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceOrderImportRequest,
) -> MarketplaceOrderDetailResponse:
    _validate_order_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
    )

    existing = detect_duplicate_order(
        session,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_order_identifier=payload.marketplace_order_identifier,
    )
    existing_transaction_refs = set()
    if existing is not None:
        existing_transaction_refs = {
            row.transaction_reference for row in _load_transactions(session, order_id=int(existing.id or 0))
        }
    result = ingest_marketplace_order(
        session,
        organization_id=organization_id,
        payload=payload,
    )
    order_id = int(result.order.id or 0)

    if existing is None:
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=order_id,
            actor_user_id=actor_user_id,
            event_type="marketplace_order_imported",
            event_payload_json={
                "marketplace_account_id": result.order.marketplace_account_id,
                "marketplace_order_identifier": result.order.marketplace_order_identifier,
                "imported_line_items": len(result.line_items),
                "imported_transactions": len(result.transactions),
            },
        )
    else:
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=order_id,
            actor_user_id=actor_user_id,
            event_type="marketplace_duplicate_order_detected",
            event_payload_json={
                "marketplace_account_id": result.order.marketplace_account_id,
                "marketplace_order_identifier": result.order.marketplace_order_identifier,
            },
        )
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=order_id,
            actor_user_id=actor_user_id,
            event_type="marketplace_order_updated",
            event_payload_json={
                "order_status": result.order.order_status,
                "order_total": str(result.order.order_total),
                "order_currency": result.order.order_currency,
            },
        )

    for transaction in result.transactions:
        if existing is not None and transaction.transaction_reference in existing_transaction_refs:
            continue
        create_order_event(
            session,
            organization_id=organization_id,
            marketplace_order_id=order_id,
            actor_user_id=actor_user_id,
            event_type="marketplace_transaction_imported",
            event_payload_json={
                "transaction_reference": transaction.transaction_reference,
                "transaction_type": transaction.transaction_type,
                "transaction_status": transaction.transaction_status,
            },
        )

    session.commit()
    session.refresh(result.order)
    events = _load_events(session, order_id=order_id)
    resolution = _validate_order_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_order_id=order_id,
        action="marketplace_order:detail",
    )
    return _detail_response(
        resolution=resolution,
        result=OrderImportResult(
            order=result.order,
            line_items=tuple(_load_line_items(session, order_id=order_id)),
            transactions=tuple(_load_transactions(session, order_id=order_id)),
            duplicate_detected=result.duplicate_detected,
        ),
        events=events,
    )


def get_marketplace_order(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    order_id: int,
) -> MarketplaceOrderDetailResponse:
    order = _order_or_404(session, organization_id=organization_id, order_id=order_id)
    resolution = _validate_order_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_order_id=order_id,
        action="marketplace_order:detail",
    )
    line_items = _load_line_items(session, order_id=order_id)
    transactions = _load_transactions(session, order_id=order_id)
    events = _load_events(session, order_id=order_id)
    summary = MarketplaceOrderImportSummaryResponse(
        order_id=order_id,
        duplicate_detected=False,
        imported_line_items=len(line_items),
        imported_transactions=len(transactions),
        order_total=order.order_total,
        order_currency=order.order_currency,
    )
    return MarketplaceOrderDetailResponse(
        order=_to_order_response(order),
        line_items=[_to_line_item_response(row) for row in line_items],
        transactions=[_to_transaction_response(row) for row in transactions],
        events=[_to_event_response(row) for row in events],
        import_summary=summary,
        permissions=_permission_response(resolution),
    )


def list_marketplace_orders(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceOrderListResponse:
    resolution = _validate_order_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="marketplace_order:list",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.organization_id == organization_id)
        .order_by(MarketplaceOrder.ordered_at.desc(), MarketplaceOrder.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total_items = len(
        session.exec(select(MarketplaceOrder.id).where(MarketplaceOrder.organization_id == organization_id)).all()
    )
    return MarketplaceOrderListResponse(
        items=[_to_order_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def list_marketplace_transactions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceTransactionListResponse:
    _validate_order_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="marketplace_order:transactions",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.organization_id == organization_id)
        .order_by(MarketplaceTransaction.created_at.desc(), MarketplaceTransaction.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total_items = len(
        session.exec(select(MarketplaceTransaction.id).where(MarketplaceTransaction.organization_id == organization_id)).all()
    )
    return MarketplaceTransactionListResponse(
        items=[_to_transaction_response(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def generate_order_summary(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> dict[str, Any]:
    resolution = _validate_order_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="marketplace_order:summary",
    )
    order_ids = session.exec(
        select(MarketplaceOrder.id).where(MarketplaceOrder.organization_id == organization_id)
    ).all()
    transaction_ids = session.exec(
        select(MarketplaceTransaction.id).where(MarketplaceTransaction.organization_id == organization_id)
    ).all()
    return {
        "permissions": _permission_response(resolution).model_dump(),
        "total_orders": len(order_ids),
        "total_transactions": len(transaction_ids),
    }


def reconcile_marketplace_orders(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceOrderReconcileRequest,
) -> MarketplaceTransactionReconciliationReportResponse:
    _validate_order_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
        action="marketplace_order:reconcile",
    )
    query = select(MarketplaceOrder).where(MarketplaceOrder.organization_id == organization_id)
    if payload.marketplace_account_id is not None:
        query = query.where(MarketplaceOrder.marketplace_account_id == payload.marketplace_account_id)
    orders = list(session.exec(query.order_by(MarketplaceOrder.ordered_at.asc(), MarketplaceOrder.id.asc())).all())
    transactions_by_order_id: dict[int, list[MarketplaceTransaction]] = {}
    for order in orders:
        order_id = int(order.id or 0)
        transactions_by_order_id[order_id] = _load_transactions(session, order_id=order_id)
    report = generate_transaction_report(
        orders=orders,
        transactions_by_order_id=transactions_by_order_id,
    )
    create_order_event(
        session,
        organization_id=organization_id,
        marketplace_order_id=None,
        actor_user_id=actor_user_id,
        event_type="marketplace_reconciliation_generated",
        event_payload_json={
            "marketplace_account_id": payload.marketplace_account_id,
            "total_orders": report.total_orders,
            "total_transactions": report.total_transactions,
            "mismatch_codes": [row.mismatch_code for row in report.mismatches],
        },
    )
    session.commit()
    return report
