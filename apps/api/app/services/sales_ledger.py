"""P36-03 deterministic realized sales ledger."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import InventoryCopy, Listing, SaleFinancialAdjustment, SaleLifecycleEvent, SaleRecord, SaleRecordLineItem
from app.models.sales_ledger import utc_now
from app.schemas.sales_ledger import (
    SaleChannelCountRow,
    SaleFinancialAdjustmentCreate,
    SaleFinancialAdjustmentListResponse,
    SaleFinancialAdjustmentRead,
    SaleLifecycleEventListResponse,
    SaleLifecycleEventRead,
    SaleRecordCreate,
    SaleRecordDetailRead,
    SaleRecordLineItemCreate,
    SaleRecordLineItemRead,
    SaleRecordListResponse,
    SaleRecordPatch,
    SaleRecordRead,
    SalesDashboardSummary,
)
from app.services.listing_registry import append_listing_event, get_listing_owner
from app.services.listing_registry import _snapshot_public_dict as listing_snapshot_public_dict  # type: ignore[attr-defined]


MONEY_QUANT = Decimal("0.01")
MARGIN_QUANT = Decimal("0.00000001")
ZERO = Decimal("0.00")
RECORDED_ELIGIBLE_LISTING_STATUSES = {"READY", "ACTIVE"}
SALE_CHANNELS = {"manual", "ebay", "whatnot", "shopify", "hipcomic", "shortboxed", "convention", "private_sale"}
SALE_STATUSES = {"DRAFT", "RECORDED", "VOIDED"}


def clamp_sale_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_channel_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in SALE_CHANNELS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid sale channel filter")
    return normalized


def _normalize_status_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized not in SALE_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid sale status filter")
    return normalized


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _margin(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MARGIN_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _sale_snapshot_public(row: SaleRecord) -> dict[str, Any]:
    return _json_safe(
        {
            "id": row.id,
            "owner_user_id": row.owner_user_id,
            "listing_id": row.listing_id,
            "channel": row.channel,
            "status": row.status,
            "sale_date": row.sale_date,
            "buyer_reference": row.buyer_reference,
            "currency": row.currency,
            "gross_sale_amount": row.gross_sale_amount,
            "item_subtotal_amount": row.item_subtotal_amount,
            "shipping_charged_amount": row.shipping_charged_amount,
            "tax_collected_amount": row.tax_collected_amount,
            "platform_fee_amount": row.platform_fee_amount,
            "payment_fee_amount": row.payment_fee_amount,
            "shipping_cost_amount": row.shipping_cost_amount,
            "other_cost_amount": row.other_cost_amount,
            "net_proceeds_amount": row.net_proceeds_amount,
            "acquisition_cost_basis_amount": row.acquisition_cost_basis_amount,
            "realized_profit_amount": row.realized_profit_amount,
            "realized_margin_pct": row.realized_margin_pct,
            "replay_key": row.replay_key,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "recorded_at": row.recorded_at,
            "voided_at": row.voided_at,
        }
    )


def _line_item_snapshot_public(row: SaleRecordLineItem) -> dict[str, Any]:
    return _json_safe(
        {
            "id": row.id,
            "sale_record_id": row.sale_record_id,
            "listing_id": row.listing_id,
            "inventory_item_id": row.inventory_item_id,
            "canonical_comic_issue_id": row.canonical_comic_issue_id,
            "quantity_sold": row.quantity_sold,
            "unit_sale_amount": row.unit_sale_amount,
            "line_subtotal_amount": row.line_subtotal_amount,
            "cost_basis_amount": row.cost_basis_amount,
            "realized_profit_amount": row.realized_profit_amount,
            "created_at": row.created_at,
        }
    )


def _adjustment_snapshot_public(row: SaleFinancialAdjustment) -> dict[str, Any]:
    return _json_safe(
        {
            "id": row.id,
            "sale_record_id": row.sale_record_id,
            "adjustment_type": row.adjustment_type,
            "amount": row.amount,
            "currency": row.currency,
            "description": row.description,
            "created_at": row.created_at,
        }
    )


def _event_read(row: SaleLifecycleEvent) -> SaleLifecycleEventRead:
    return SaleLifecycleEventRead.model_validate(row, from_attributes=True)


def _line_item_read(row: SaleRecordLineItem) -> SaleRecordLineItemRead:
    return SaleRecordLineItemRead.model_validate(row, from_attributes=True)


def _adjustment_read(row: SaleFinancialAdjustment) -> SaleFinancialAdjustmentRead:
    return SaleFinancialAdjustmentRead.model_validate(row, from_attributes=True)


def _sale_read(
    row: SaleRecord,
    *,
    event_count: int = 0,
    line_item_count: int = 0,
    adjustment_count: int = 0,
) -> SaleRecordRead:
    return SaleRecordRead(
        id=int(row.id),
        owner_user_id=int(row.owner_user_id),
        listing_id=row.listing_id,
        channel=str(row.channel),
        status=str(row.status),
        sale_date=row.sale_date,
        buyer_reference=row.buyer_reference,
        currency=str(row.currency),
        gross_sale_amount=row.gross_sale_amount,
        item_subtotal_amount=row.item_subtotal_amount,
        shipping_charged_amount=row.shipping_charged_amount,
        tax_collected_amount=row.tax_collected_amount,
        platform_fee_amount=row.platform_fee_amount,
        payment_fee_amount=row.payment_fee_amount,
        shipping_cost_amount=row.shipping_cost_amount,
        other_cost_amount=row.other_cost_amount,
        net_proceeds_amount=row.net_proceeds_amount,
        acquisition_cost_basis_amount=row.acquisition_cost_basis_amount,
        realized_profit_amount=row.realized_profit_amount,
        realized_margin_pct=row.realized_margin_pct,
        replay_key=row.replay_key,
        created_at=row.created_at,
        updated_at=row.updated_at,
        recorded_at=row.recorded_at,
        voided_at=row.voided_at,
        event_count=event_count,
        line_item_count=line_item_count,
        adjustment_count=adjustment_count,
    )


def _detail_read(
    row: SaleRecord,
    *,
    items: list[SaleRecordLineItem],
    adjustments: list[SaleFinancialAdjustment],
    events: list[SaleLifecycleEvent],
) -> SaleRecordDetailRead:
    base = _sale_read(
        row,
        event_count=len(events),
        line_item_count=len(items),
        adjustment_count=len(adjustments),
    )
    return SaleRecordDetailRead.model_validate(
        {
            **base.model_dump(),
            "line_items": [_line_item_read(item).model_dump() for item in items],
            "financial_adjustments": [_adjustment_read(adj).model_dump() for adj in adjustments],
            "events": [_event_read(evt).model_dump() for evt in events],
        }
    )


def _replay_lookup_sale(session: Session, *, owner_user_id: int, replay_key: str) -> SaleRecord | None:
    return session.exec(
        select(SaleRecord).where(
            SaleRecord.owner_user_id == owner_user_id,
            SaleRecord.replay_key == replay_key,
        )
    ).first()


def _load_sale_counts(session: Session, sale_ids: list[int]) -> dict[int, dict[str, int]]:
    if not sale_ids:
        return {}
    ids = list(dict.fromkeys(int(i) for i in sale_ids))

    def _rows_to_map(rows: list[tuple[int, int]]) -> dict[int, int]:
        return {int(k): int(v) for k, v in rows}

    event_counts = _rows_to_map(
        list(
            session.exec(
                select(SaleLifecycleEvent.sale_record_id, func.count(SaleLifecycleEvent.id))
                .where(SaleLifecycleEvent.sale_record_id.in_(ids))
                .group_by(SaleLifecycleEvent.sale_record_id)
            ).all()
        )
    )
    item_counts = _rows_to_map(
        list(
            session.exec(
                select(SaleRecordLineItem.sale_record_id, func.count(SaleRecordLineItem.id))
                .where(SaleRecordLineItem.sale_record_id.in_(ids))
                .group_by(SaleRecordLineItem.sale_record_id)
            ).all()
        )
    )
    adjustment_counts = _rows_to_map(
        list(
            session.exec(
                select(SaleFinancialAdjustment.sale_record_id, func.count(SaleFinancialAdjustment.id))
                .where(SaleFinancialAdjustment.sale_record_id.in_(ids))
                .group_by(SaleFinancialAdjustment.sale_record_id)
            ).all()
        )
    )
    return {
        sale_id: {
            "event_count": event_counts.get(sale_id, 0),
            "line_item_count": item_counts.get(sale_id, 0),
            "adjustment_count": adjustment_counts.get(sale_id, 0),
        }
        for sale_id in ids
    }


def build_sale_detail(
    session: Session,
    *,
    owner_user_id: int,
    sale_id: int,
    include_children: bool = True,
    allow_cross_owner_ops: bool = False,
) -> SaleRecordDetailRead:
    row = session.get(SaleRecord, sale_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if int(row.owner_user_id) != owner_user_id and not allow_cross_owner_ops:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")

    if not include_children:
        return _detail_read(row, items=[], adjustments=[], events=[])

    items = session.exec(
        select(SaleRecordLineItem)
        .where(SaleRecordLineItem.sale_record_id == sale_id)
        .order_by(col(SaleRecordLineItem.id).asc())
    ).all()
    adjustments = session.exec(
        select(SaleFinancialAdjustment)
        .where(SaleFinancialAdjustment.sale_record_id == sale_id)
        .order_by(col(SaleFinancialAdjustment.created_at).asc())
        .order_by(col(SaleFinancialAdjustment.id).asc())
    ).all()
    events = session.exec(
        select(SaleLifecycleEvent)
        .where(SaleLifecycleEvent.sale_record_id == sale_id)
        .order_by(col(SaleLifecycleEvent.created_at).asc())
        .order_by(col(SaleLifecycleEvent.id).asc())
    ).all()
    return _detail_read(row, items=items, adjustments=adjustments, events=events)


def _resolve_sale_listing_id(payload: SaleRecordCreate) -> int | None:
    listing_ids = {int(payload.listing_id)} if payload.listing_id is not None else set()
    for line_item in payload.line_items:
        if line_item.listing_id is not None:
            listing_ids.add(int(line_item.listing_id))
    if len(listing_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="sale line items may reference at most one listing in this phase",
        )
    return next(iter(listing_ids)) if listing_ids else None


def _resolve_sale_currency(payload: SaleRecordCreate | SaleRecordPatch) -> str | None:
    currency = getattr(payload, "currency", None)
    if currency is None:
        return None
    return str(currency).strip().upper()


def _normalize_line_items(
    *,
    sale_listing_id: int | None,
    line_items: list[SaleRecordLineItemCreate],
    listing_cost_basis_amount: Decimal | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for line_item in line_items:
        item_listing_id = int(line_item.listing_id) if line_item.listing_id is not None else sale_listing_id
        subtotal = _money(line_item.line_subtotal_amount) if line_item.line_subtotal_amount is not None else _money(
            _decimal(line_item.unit_sale_amount) * Decimal(line_item.quantity_sold)
        )
        if line_item.line_subtotal_amount is not None and subtotal != _money(line_item.line_subtotal_amount):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="line_subtotal_amount must match quantity_sold × unit_sale_amount",
            )
        if line_item.cost_basis_amount is not None:
            cost_basis = _money(line_item.cost_basis_amount)
        elif item_listing_id is not None and listing_cost_basis_amount is not None:
            cost_basis = _money(listing_cost_basis_amount * Decimal(line_item.quantity_sold))
        else:
            cost_basis = None
        normalized.append(
            {
                "listing_id": item_listing_id,
                "inventory_item_id": line_item.inventory_item_id,
                "canonical_comic_issue_id": line_item.canonical_comic_issue_id,
                "quantity_sold": int(line_item.quantity_sold),
                "unit_sale_amount": _money(line_item.unit_sale_amount),
                "line_subtotal_amount": subtotal,
                "cost_basis_amount": cost_basis,
            }
        )
    normalized.sort(
        key=lambda row: (
            row["listing_id"] is None,
            row["listing_id"] or 0,
            row["inventory_item_id"] is None,
            row["inventory_item_id"] or 0,
            row["canonical_comic_issue_id"] is None,
            row["canonical_comic_issue_id"] or 0,
            row["quantity_sold"],
            str(row["unit_sale_amount"]),
            str(row["line_subtotal_amount"]),
            str(row["cost_basis_amount"]) if row["cost_basis_amount"] is not None else "",
        )
    )
    return normalized


def _normalize_adjustments(
    *, adjustments: list[SaleFinancialAdjustmentCreate], sale_currency: str
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for adjustment in adjustments:
        currency = str(adjustment.currency).strip().upper()
        if currency != sale_currency:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="all sale adjustments must use the sale currency",
            )
        normalized.append(
            {
                "adjustment_type": str(adjustment.adjustment_type),
                "amount": _money(adjustment.amount),
                "currency": currency,
                "description": adjustment.description.strip() if adjustment.description else None,
            }
        )
    normalized.sort(key=lambda row: (row["adjustment_type"], str(row["amount"]), row["description"] or ""))
    return normalized


def _adjustment_total(adjustments: list[dict[str, Any]], *types: str) -> Decimal:
    wanted = set(types)
    return _money(sum((_decimal(row["amount"]) for row in adjustments if row["adjustment_type"] in wanted), ZERO))


def _calculate_totals(
    *,
    line_items: list[dict[str, Any]],
    adjustments: list[dict[str, Any]],
    acquisition_cost_basis_amount: Decimal | None,
) -> dict[str, Decimal | None]:
    item_subtotal = _money(sum((_decimal(row["line_subtotal_amount"]) for row in line_items), ZERO))
    shipping_charged = _adjustment_total(adjustments, "shipping_charged")
    tax_collected = _adjustment_total(adjustments, "tax_collected")
    discount = _adjustment_total(adjustments, "discount")
    refund = _adjustment_total(adjustments, "refund")
    platform_fee = _adjustment_total(adjustments, "platform_fee")
    payment_fee = _adjustment_total(adjustments, "payment_fee")
    shipping_cost = _adjustment_total(adjustments, "shipping_cost")
    other_cost = _adjustment_total(adjustments, "other")
    gross = _money(item_subtotal + shipping_charged + tax_collected - discount - refund)
    net = _money(gross - platform_fee - payment_fee - shipping_cost - other_cost)
    profit = None if acquisition_cost_basis_amount is None else _money(net - acquisition_cost_basis_amount)
    margin = None if profit is None or gross == ZERO else _margin(profit / gross)
    return {
        "item_subtotal_amount": item_subtotal,
        "shipping_charged_amount": shipping_charged,
        "tax_collected_amount": tax_collected,
        "platform_fee_amount": platform_fee,
        "payment_fee_amount": payment_fee,
        "shipping_cost_amount": shipping_cost,
        "other_cost_amount": other_cost,
        "gross_sale_amount": gross,
        "net_proceeds_amount": net,
        "realized_profit_amount": profit,
        "realized_margin_pct": margin,
    }


def _linked_listing_cost_basis(session: Session, listing_id: int | None) -> Decimal | None:
    if listing_id is None:
        return None
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="linked listing not found")
    inv = session.get(InventoryCopy, listing.inventory_copy_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="linked inventory copy not found")
    return _money(inv.acquisition_cost)


def _persist_sale_children(
    session: Session,
    *,
    sale_id: int,
    line_items: list[dict[str, Any]],
    adjustments: list[dict[str, Any]],
) -> None:
    for row in line_items:
        session.add(
            SaleRecordLineItem(
                sale_record_id=sale_id,
                listing_id=row["listing_id"],
                inventory_item_id=row["inventory_item_id"],
                canonical_comic_issue_id=row["canonical_comic_issue_id"],
                quantity_sold=row["quantity_sold"],
                unit_sale_amount=row["unit_sale_amount"],
                line_subtotal_amount=row["line_subtotal_amount"],
                cost_basis_amount=row["cost_basis_amount"],
                realized_profit_amount=None if row["cost_basis_amount"] is None else _money(row["line_subtotal_amount"] - row["cost_basis_amount"]),
                created_at=utc_now(),
            )
        )
    for row in adjustments:
        session.add(
            SaleFinancialAdjustment(
                sale_record_id=sale_id,
                adjustment_type=row["adjustment_type"],
                amount=row["amount"],
                currency=row["currency"],
                description=row["description"],
                created_at=utc_now(),
            )
        )


def _sale_line_items(session: Session, sale_id: int) -> list[SaleRecordLineItem]:
    return session.exec(
        select(SaleRecordLineItem)
        .where(SaleRecordLineItem.sale_record_id == sale_id)
        .order_by(col(SaleRecordLineItem.id).asc())
    ).all()


def _sale_adjustments(session: Session, sale_id: int) -> list[SaleFinancialAdjustment]:
    return session.exec(
        select(SaleFinancialAdjustment)
        .where(SaleFinancialAdjustment.sale_record_id == sale_id)
        .order_by(col(SaleFinancialAdjustment.created_at).asc())
        .order_by(col(SaleFinancialAdjustment.id).asc())
    ).all()


def _sale_events(session: Session, sale_id: int) -> list[SaleLifecycleEvent]:
    return session.exec(
        select(SaleLifecycleEvent)
        .where(SaleLifecycleEvent.sale_record_id == sale_id)
        .order_by(col(SaleLifecycleEvent.created_at).asc())
        .order_by(col(SaleLifecycleEvent.id).asc())
    ).all()


def _append_sale_event(
    session: Session,
    *,
    sale_id: int,
    event_type: str,
    prior_status: str | None,
    new_status: str | None,
    created_by_user_id: int | None,
    metadata_json: dict[str, Any],
) -> None:
    session.add(
        SaleLifecycleEvent(
            sale_record_id=sale_id,
            event_type=event_type,
            prior_status=prior_status,
            new_status=new_status,
            metadata_json=_json_safe(metadata_json),
            created_by_user_id=created_by_user_id,
            created_at=utc_now(),
        )
    )


def _maybe_mark_listing_sold(
    session: Session,
    *,
    sale: SaleRecord,
    owner_user_id: int,
    sale_listing_id: int | None,
) -> None:
    if sale_listing_id is None:
        return
    listing = get_listing_owner(session, listing_id=sale_listing_id, owner_user_id=owner_user_id)
    if listing.status == "SOLD":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="linked listing is already SOLD")
    if listing.status not in RECORDED_ELIGIBLE_LISTING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"linked listing must be READY or ACTIVE to record a sale (currently {listing.status})",
        )

    prior_status = listing.status
    now_ts = utc_now()
    listing.status = "SOLD"
    listing.sold_at = now_ts
    listing.updated_at = now_ts
    sale_snapshot = _sale_snapshot_public(sale)
    listing_snapshot = type("_ListingSnapshot", (), {})()
    listing_snapshot.source_type = listing.source_type
    listing_snapshot.title = listing.title
    listing_snapshot.description = listing.description
    listing_snapshot.condition_summary = listing.condition_summary
    listing_snapshot.asking_price_amount = listing.asking_price_amount
    listing_snapshot.asking_price_currency = listing.asking_price_currency
    listing_snapshot.quantity = int(listing.quantity)
    listing_snapshot.canonical_comic_issue_id = listing.canonical_comic_issue_id
    listing_meta = {
        "sale_record": sale_snapshot,
        "listing_before": _json_safe(
            {
                "status": prior_status,
                "sold_at": None,
                "title": listing.title,
                "source_type": listing.source_type,
                "asking_price_amount": getattr(listing, "asking_price_amount", None),
                "asking_price_currency": getattr(listing, "asking_price_currency", None),
            }
        ),
        "listing_after": _json_safe(
            {
                "status": listing.status,
                "sold_at": listing.sold_at,
                "title": listing.title,
                "source_type": listing.source_type,
                "asking_price_amount": getattr(listing, "asking_price_amount", None),
                "asking_price_currency": getattr(listing, "asking_price_currency", None),
            }
        ),
        "listing_snapshot": listing_snapshot_public_dict(listing_snapshot),
    }
    append_listing_event(
        session,
        listing_id=int(listing.id),
        event_type="SOLD",
        prior_status=prior_status,
        new_status="SOLD",
        created_by_user_id=owner_user_id,
        metadata_json=listing_meta,
        replay_key=f"{sale.replay_key}:sold_evt" if sale.replay_key else None,
    )


def create_sale(
    session: Session,
    *,
    owner_user_id: int,
    payload: SaleRecordCreate | dict,
) -> tuple[SaleRecordDetailRead, bool]:
    if not isinstance(payload, SaleRecordCreate):
        payload = SaleRecordCreate.model_validate(payload)

    channel = str(payload.channel).strip().lower()
    if channel not in SALE_CHANNELS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid sale channel")
    currency = str(payload.currency).strip().upper()
    sale_listing_id = _resolve_sale_listing_id(payload)

    if payload.replay_key:
        dup = _replay_lookup_sale(session, owner_user_id=owner_user_id, replay_key=payload.replay_key)
        if dup is not None:
            return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(dup.id)), True

    listing_cost_basis = _linked_listing_cost_basis(session, sale_listing_id)
    line_items = _normalize_line_items(
        sale_listing_id=sale_listing_id,
        line_items=payload.line_items,
        listing_cost_basis_amount=listing_cost_basis,
    )
    adjustments = _normalize_adjustments(adjustments=payload.financial_adjustments, sale_currency=currency)
    acquisition_cost_basis_amount = None
    if any(row["cost_basis_amount"] is not None for row in line_items):
        acquisition_cost_basis_amount = _money(
            sum((_decimal(row["cost_basis_amount"]) for row in line_items if row["cost_basis_amount"] is not None), ZERO)
        )
    elif listing_cost_basis is not None:
        acquisition_cost_basis_amount = _money(
            sum(
                (_money(listing_cost_basis * Decimal(row["quantity_sold"])) for row in line_items),
                ZERO,
            )
        )

    totals = _calculate_totals(
        line_items=line_items,
        adjustments=adjustments,
        acquisition_cost_basis_amount=acquisition_cost_basis_amount,
    )

    sale = SaleRecord(
        owner_user_id=owner_user_id,
        listing_id=sale_listing_id,
        channel=channel,
        status="DRAFT",
        sale_date=payload.sale_date,
        buyer_reference=payload.buyer_reference,
        currency=currency,
        gross_sale_amount=totals["gross_sale_amount"] or ZERO,
        item_subtotal_amount=totals["item_subtotal_amount"] or ZERO,
        shipping_charged_amount=totals["shipping_charged_amount"] or ZERO,
        tax_collected_amount=totals["tax_collected_amount"] or ZERO,
        platform_fee_amount=totals["platform_fee_amount"] or ZERO,
        payment_fee_amount=totals["payment_fee_amount"] or ZERO,
        shipping_cost_amount=totals["shipping_cost_amount"] or ZERO,
        other_cost_amount=totals["other_cost_amount"] or ZERO,
        net_proceeds_amount=totals["net_proceeds_amount"] or ZERO,
        acquisition_cost_basis_amount=acquisition_cost_basis_amount,
        realized_profit_amount=totals["realized_profit_amount"],
        realized_margin_pct=totals["realized_margin_pct"],
        replay_key=payload.replay_key,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(sale)

    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if payload.replay_key:
            dup = _replay_lookup_sale(session, owner_user_id=owner_user_id, replay_key=payload.replay_key)
            if dup is not None:
                return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(dup.id)), True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sale replay collision")

    if sale.id is None:
        raise RuntimeError("sale row was not flushed")

    _persist_sale_children(session, sale_id=int(sale.id), line_items=line_items, adjustments=adjustments)
    _append_sale_event(
        session,
        sale_id=int(sale.id),
        event_type="CREATED",
        prior_status=None,
        new_status="DRAFT",
        created_by_user_id=owner_user_id,
        metadata_json={
            "sale": _sale_snapshot_public(sale),
            "line_items": line_items,
            "financial_adjustments": adjustments,
        },
    )

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if payload.replay_key:
            dup = _replay_lookup_sale(session, owner_user_id=owner_user_id, replay_key=payload.replay_key)
            if dup is not None:
                return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(dup.id)), True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sale create collision")

    return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(sale.id)), False


def update_sale(
    session: Session,
    *,
    owner_user_id: int,
    sale_id: int,
    payload: SaleRecordPatch | dict,
) -> SaleRecordDetailRead:
    if not isinstance(payload, SaleRecordPatch):
        payload = SaleRecordPatch.model_validate(payload)

    sale = session.get(SaleRecord, sale_id)
    if sale is None or int(sale.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if sale.status != "DRAFT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sale may only be patched while DRAFT")

    before = _sale_snapshot_public(sale)
    if payload.channel is not None:
        channel = str(payload.channel).strip().lower()
        if channel not in SALE_CHANNELS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid sale channel")
        sale.channel = channel
    if payload.sale_date is not None:
        sale.sale_date = payload.sale_date
    if payload.currency is not None:
        sale.currency = str(payload.currency).strip().upper()
    if payload.buyer_reference is not None:
        sale.buyer_reference = payload.buyer_reference
    if payload.listing_id is not None:
        sale.listing_id = payload.listing_id

    sale.updated_at = utc_now()
    after = _sale_snapshot_public(sale)
    if before != after:
        _append_sale_event(
            session,
            sale_id=int(sale.id),
            event_type="UPDATED",
            prior_status="DRAFT",
            new_status="DRAFT",
            created_by_user_id=owner_user_id,
            metadata_json={"before": before, "after": after},
        )
    session.add(sale)
    session.commit()
    return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(sale.id))


def record_sale(
    session: Session,
    *,
    owner_user_id: int,
    sale_id: int,
) -> SaleRecordDetailRead:
    sale = session.get(SaleRecord, sale_id)
    if sale is None or int(sale.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if sale.status != "DRAFT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sale has already been recorded or voided")

    line_items = _sale_line_items(session, sale_id)
    adjustments = _sale_adjustments(session, sale_id)
    if not line_items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sale requires at least one line item")

    sale_listing_id = sale.listing_id
    if sale_listing_id is None:
        sale_listing_ids = {item.listing_id for item in line_items if item.listing_id is not None}
        if len(sale_listing_ids) == 1:
            sale_listing_id = next(iter(sale_listing_ids))
    listing_cost_basis = _linked_listing_cost_basis(session, sale_listing_id)

    normalized_items: list[dict[str, Any]] = []
    for item in line_items:
        cost_basis = item.cost_basis_amount
        if cost_basis is None and listing_cost_basis is not None:
            cost_basis = _money(listing_cost_basis * Decimal(item.quantity_sold))
        normalized_items.append(
            {
                "listing_id": item.listing_id,
                "inventory_item_id": item.inventory_item_id,
                "canonical_comic_issue_id": item.canonical_comic_issue_id,
                "quantity_sold": item.quantity_sold,
                "unit_sale_amount": _money(item.unit_sale_amount),
                "line_subtotal_amount": _money(item.line_subtotal_amount),
                "cost_basis_amount": cost_basis,
            }
        )
    normalized_adjustments = [
        {"adjustment_type": adj.adjustment_type, "amount": _money(adj.amount), "currency": str(adj.currency).upper(), "description": adj.description}
        for adj in adjustments
    ]

    acquisition_cost_basis_amount = None
    cost_basis_values = [row["cost_basis_amount"] for row in normalized_items if row["cost_basis_amount"] is not None]
    if cost_basis_values:
        acquisition_cost_basis_amount = _money(sum((_decimal(v) for v in cost_basis_values), ZERO))
    elif listing_cost_basis is not None:
        acquisition_cost_basis_amount = _money(sum((_money(listing_cost_basis * Decimal(row["quantity_sold"])) for row in normalized_items), ZERO))

    totals = _calculate_totals(
        line_items=normalized_items,
        adjustments=normalized_adjustments,
        acquisition_cost_basis_amount=acquisition_cost_basis_amount,
    )
    sale.item_subtotal_amount = totals["item_subtotal_amount"] or ZERO
    sale.shipping_charged_amount = totals["shipping_charged_amount"] or ZERO
    sale.tax_collected_amount = totals["tax_collected_amount"] or ZERO
    sale.platform_fee_amount = totals["platform_fee_amount"] or ZERO
    sale.payment_fee_amount = totals["payment_fee_amount"] or ZERO
    sale.shipping_cost_amount = totals["shipping_cost_amount"] or ZERO
    sale.other_cost_amount = totals["other_cost_amount"] or ZERO
    sale.gross_sale_amount = totals["gross_sale_amount"] or ZERO
    sale.net_proceeds_amount = totals["net_proceeds_amount"] or ZERO
    sale.acquisition_cost_basis_amount = acquisition_cost_basis_amount
    sale.realized_profit_amount = totals["realized_profit_amount"]
    sale.realized_margin_pct = totals["realized_margin_pct"]
    sale.status = "RECORDED"
    sale.recorded_at = utc_now()
    sale.updated_at = utc_now()
    session.add(sale)

    _append_sale_event(
        session,
        sale_id=int(sale.id),
        event_type="RECORDED",
        prior_status="DRAFT",
        new_status="RECORDED",
        created_by_user_id=owner_user_id,
        metadata_json={
            "sale": _sale_snapshot_public(sale),
            "line_items": [_line_item_snapshot_public(item) for item in line_items],
            "financial_adjustments": [_adjustment_snapshot_public(adj) for adj in adjustments],
        },
    )
    _maybe_mark_listing_sold(session, sale=sale, owner_user_id=owner_user_id, sale_listing_id=sale_listing_id)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="record sale collision") from exc
    return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(sale.id))


def void_sale(
    session: Session,
    *,
    owner_user_id: int,
    sale_id: int,
) -> SaleRecordDetailRead:
    sale = session.get(SaleRecord, sale_id)
    if sale is None or int(sale.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if sale.status == "VOIDED":
        return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(sale.id))

    prior_status = sale.status
    sale.status = "VOIDED"
    sale.voided_at = utc_now()
    sale.updated_at = utc_now()
    session.add(sale)
    _append_sale_event(
        session,
        sale_id=int(sale.id),
        event_type="VOIDED",
        prior_status=prior_status,
        new_status="VOIDED",
        created_by_user_id=owner_user_id,
        metadata_json={"sale": _sale_snapshot_public(sale)},
    )
    session.commit()
    return build_sale_detail(session, owner_user_id=owner_user_id, sale_id=int(sale.id))


def list_sales_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
    channel: str | None = None,
    status: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> tuple[list[SaleRecord], int]:
    channel = _normalize_channel_filter(channel)
    status = _normalize_status_filter(status)
    q = select(SaleRecord).where(SaleRecord.owner_user_id == owner_user_id)
    c = select(func.count(SaleRecord.id)).where(SaleRecord.owner_user_id == owner_user_id)
    if channel is not None:
        q = q.where(SaleRecord.channel == channel)
        c = c.where(SaleRecord.channel == channel)
    if status is not None:
        q = q.where(SaleRecord.status == status)
        c = c.where(SaleRecord.status == status)
    if sale_date_from is not None:
        q = q.where(SaleRecord.sale_date >= sale_date_from)
        c = c.where(SaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        q = q.where(SaleRecord.sale_date <= sale_date_to)
        c = c.where(SaleRecord.sale_date <= sale_date_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(SaleRecord.sale_date).desc()).order_by(col(SaleRecord.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_sales_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
    channel: str | None = None,
    status: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> tuple[list[SaleRecord], int]:
    channel = _normalize_channel_filter(channel)
    status = _normalize_status_filter(status)
    q = select(SaleRecord)
    c = select(func.count(SaleRecord.id))
    if owner_user_id is not None:
        q = q.where(SaleRecord.owner_user_id == owner_user_id)
        c = c.where(SaleRecord.owner_user_id == owner_user_id)
    if channel is not None:
        q = q.where(SaleRecord.channel == channel)
        c = c.where(SaleRecord.channel == channel)
    if status is not None:
        q = q.where(SaleRecord.status == status)
        c = c.where(SaleRecord.status == status)
    if sale_date_from is not None:
        q = q.where(SaleRecord.sale_date >= sale_date_from)
        c = c.where(SaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        q = q.where(SaleRecord.sale_date <= sale_date_to)
        c = c.where(SaleRecord.sale_date <= sale_date_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(SaleRecord.sale_date).desc()).order_by(col(SaleRecord.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_sale_events_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    channel: str | None,
    status: str | None,
    sale_date_from: date | None,
    sale_date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[SaleLifecycleEvent], int]:
    channel = _normalize_channel_filter(channel)
    status = _normalize_status_filter(status)
    q = select(SaleLifecycleEvent).join(SaleRecord, SaleLifecycleEvent.sale_record_id == SaleRecord.id)
    c = select(func.count(SaleLifecycleEvent.id)).select_from(SaleLifecycleEvent).join(
        SaleRecord, SaleLifecycleEvent.sale_record_id == SaleRecord.id
    )
    if owner_user_id is not None:
        q = q.where(SaleRecord.owner_user_id == owner_user_id)
        c = c.where(SaleRecord.owner_user_id == owner_user_id)
    if channel is not None:
        q = q.where(SaleRecord.channel == channel)
        c = c.where(SaleRecord.channel == channel)
    if status is not None:
        q = q.where(SaleRecord.status == status)
        c = c.where(SaleRecord.status == status)
    if sale_date_from is not None:
        q = q.where(SaleRecord.sale_date >= sale_date_from)
        c = c.where(SaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        q = q.where(SaleRecord.sale_date <= sale_date_to)
        c = c.where(SaleRecord.sale_date <= sale_date_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(SaleLifecycleEvent.created_at).desc())
        .order_by(col(SaleLifecycleEvent.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_sale_adjustments_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    channel: str | None,
    status: str | None,
    sale_date_from: date | None,
    sale_date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[SaleFinancialAdjustment], int]:
    channel = _normalize_channel_filter(channel)
    status = _normalize_status_filter(status)
    q = select(SaleFinancialAdjustment).join(SaleRecord, SaleFinancialAdjustment.sale_record_id == SaleRecord.id)
    c = select(func.count(SaleFinancialAdjustment.id)).select_from(SaleFinancialAdjustment).join(
        SaleRecord, SaleFinancialAdjustment.sale_record_id == SaleRecord.id
    )
    if owner_user_id is not None:
        q = q.where(SaleRecord.owner_user_id == owner_user_id)
        c = c.where(SaleRecord.owner_user_id == owner_user_id)
    if channel is not None:
        q = q.where(SaleRecord.channel == channel)
        c = c.where(SaleRecord.channel == channel)
    if status is not None:
        q = q.where(SaleRecord.status == status)
        c = c.where(SaleRecord.status == status)
    if sale_date_from is not None:
        q = q.where(SaleRecord.sale_date >= sale_date_from)
        c = c.where(SaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        q = q.where(SaleRecord.sale_date <= sale_date_to)
        c = c.where(SaleRecord.sale_date <= sale_date_to)
    total = int(session.exec(c).one())
    rows = session.exec(
        q.order_by(col(SaleFinancialAdjustment.created_at).desc())
        .order_by(col(SaleFinancialAdjustment.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> SalesDashboardSummary:
    recorded_total = int(
        session.exec(
            select(func.count(SaleRecord.id)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
            )
        ).one()
    )
    zero = ZERO
    gross = _money(
        session.exec(
            select(func.coalesce(func.sum(SaleRecord.gross_sale_amount), zero)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
            )
        ).one()
    )
    net = _money(
        session.exec(
            select(func.coalesce(func.sum(SaleRecord.net_proceeds_amount), zero)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
            )
        ).one()
    )
    profit = _money(
        session.exec(
            select(func.coalesce(func.sum(SaleRecord.realized_profit_amount), zero)).where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
            )
        ).one()
    )
    recent_rows = session.exec(
        select(SaleRecord)
        .where(SaleRecord.owner_user_id == owner_user_id, SaleRecord.status == "RECORDED")
        .order_by(col(SaleRecord.sale_date).desc())
        .order_by(col(SaleRecord.id).desc())
        .limit(10)
    ).all()
    counts = session.exec(
        select(SaleRecord.channel, func.count(SaleRecord.id))
        .where(SaleRecord.owner_user_id == owner_user_id, SaleRecord.status == "RECORDED")
        .group_by(SaleRecord.channel)
        .order_by(SaleRecord.channel.asc())
    ).all()
    count_rows = [SaleChannelCountRow(channel=str(channel), count=int(count)) for channel, count in counts]
    sale_counts = _load_sale_counts(session, [int(row.id) for row in recent_rows])
    recent_sales = [
        _sale_read(
            row,
            event_count=sale_counts.get(int(row.id), {}).get("event_count", 0),
            line_item_count=sale_counts.get(int(row.id), {}).get("line_item_count", 0),
            adjustment_count=sale_counts.get(int(row.id), {}).get("adjustment_count", 0),
        )
        for row in recent_rows
    ]
    return SalesDashboardSummary(
        completed_sale_count=recorded_total,
        gross_sales_total=gross,
        net_proceeds_total=net,
        realized_profit_total=profit,
        recent_sales=recent_sales,
        sales_count_by_channel=count_rows,
    )

