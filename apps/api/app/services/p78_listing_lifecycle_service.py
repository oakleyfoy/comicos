"""P78-02 listing publication, sync, reservations, and sales."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.p78_marketplace_lifecycle import (
    P78InventoryReservation,
    P78Listing,
    P78SaleRecord,
    utc_now,
)
from app.models.p78_sell_workflow import P78ListingDraft
from app.schemas.p78_marketplace import (
    P78ListingListResponse,
    P78ListingPublishRead,
    P78ListingRead,
    P78ListingSyncRead,
    P78ListingUpdate,
    P78SaleListResponse,
    P78SaleRecordRead,
)
from app.models.recommendation_outcome import P73RecommendationOutcome
from app.services.storage_copy_meta import copy_display_meta

EBAY_FEE_RATE = 0.12
DEFAULT_SHIPPING = 5.0


def _to_listing_read(row: P78Listing, *, available_hint: int | None = None) -> P78ListingRead:
    return P78ListingRead(
        id=int(row.id or 0),
        listing_draft_id=int(row.listing_draft_id),
        owner_user_id=int(row.owner_user_id),
        inventory_copy_id=row.inventory_copy_id,
        lifecycle_status=row.lifecycle_status,  # type: ignore[arg-type]
        sync_state=row.sync_state,  # type: ignore[arg-type]
        marketplace=row.marketplace,
        external_listing_id=row.external_listing_id,
        listing_url=row.listing_url,
        title=row.title,
        description=row.description,
        condition_label=row.condition_label,
        asking_price=float(row.asking_price),
        sold_price=row.sold_price,
        quantity_listed=int(row.quantity_listed),
        quantity_reserved=int(row.quantity_reserved),
        fees=float(row.fees),
        shipping_cost=float(row.shipping_cost),
        listed_at=row.listed_at,
        sold_at=row.sold_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        available_copies_hint=available_hint,
    )


def _available_variant_copies(session: Session, *, owner_user_id: int, variant_id: int) -> list[InventoryCopy]:
    rows = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == owner_user_id)
        .where(InventoryCopy.variant_id == variant_id)
    ).all()
    reserved_ids = set(
        session.exec(
            select(P78InventoryReservation.inventory_copy_id).where(
                P78InventoryReservation.owner_user_id == owner_user_id,
                P78InventoryReservation.active == True,  # noqa: E712
            )
        ).all()
    )
    return [
        c
        for c in rows
        if int(c.id or 0) not in reserved_ids and (c.hold_status or "") not in {"listed", "sold"}
    ]


def _reserve_copies(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    anchor_copy: InventoryCopy,
    quantity: int,
) -> list[int]:
    if anchor_copy.variant_id is None:
        raise HTTPException(status_code=422, detail="Inventory copy missing variant.")
    pool = _available_variant_copies(session, owner_user_id=owner_user_id, variant_id=int(anchor_copy.variant_id))
    pool.sort(key=lambda c: int(c.copy_number or 0))
    if len(pool) < quantity:
        raise HTTPException(status_code=422, detail=f"Insufficient available copies to reserve {quantity}.")
    reserved: list[int] = []
    now = utc_now()
    for copy in pool[:quantity]:
        session.add(
            P78InventoryReservation(
                owner_user_id=owner_user_id,
                listing_id=listing_id,
                inventory_copy_id=int(copy.id or 0),
                quantity=1,
                active=True,
                created_at=now,
            )
        )
        copy.hold_status = "listed"
        session.add(copy)
        reserved.append(int(copy.id or 0))
    return reserved


def _release_reservations(session: Session, *, listing_id: int) -> None:
    rows = session.exec(
        select(P78InventoryReservation).where(
            P78InventoryReservation.listing_id == listing_id,
            P78InventoryReservation.active == True,  # noqa: E712
        )
    ).all()
    now = utc_now()
    for row in rows:
        row.active = False
        row.released_at = now
        session.add(row)


def list_listings(
    session: Session,
    *,
    owner_user_id: int,
    lifecycle_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> P78ListingListResponse:
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    stmt = select(P78Listing).where(P78Listing.owner_user_id == owner_user_id)
    if lifecycle_status:
        stmt = stmt.where(P78Listing.lifecycle_status == lifecycle_status.strip().upper())
    rows = list(session.exec(stmt.order_by(P78Listing.updated_at.desc(), P78Listing.id.desc())).all())
    items: list[P78ListingRead] = []
    for row in rows[off : off + lim]:
        hint = None
        if row.inventory_copy_id and row.lifecycle_status in {"LISTED", "READY"}:
            copy = session.get(InventoryCopy, row.inventory_copy_id)
            if copy and copy.variant_id:
                hint = len(_available_variant_copies(session, owner_user_id=owner_user_id, variant_id=int(copy.variant_id)))
        items.append(_to_listing_read(row, available_hint=hint))
    return P78ListingListResponse(items=items, total_items=len(rows), limit=lim, offset=off)


def get_listing(session: Session, *, owner_user_id: int, listing_id: int) -> P78ListingRead:
    row = session.get(P78Listing, listing_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return _to_listing_read(row)


def update_listing(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    payload: P78ListingUpdate,
) -> P78ListingRead:
    row = session.get(P78Listing, listing_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Listing not found.")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.flush()
    return _to_listing_read(row)


def publish_listing(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    price_mode: str = "market",
) -> P78ListingPublishRead:
    """Publish from listing draft id (path param is draft id until a row exists)."""
    draft = session.get(P78ListingDraft, listing_id)
    if draft is None or draft.owner_user_id != owner_user_id:
        existing = session.get(P78Listing, listing_id)
        if existing and existing.owner_user_id == owner_user_id:
            raise HTTPException(status_code=409, detail="Listing already published.")
        raise HTTPException(status_code=404, detail="Listing draft not found.")
    if draft.status == "ARCHIVED":
        raise HTTPException(status_code=422, detail="Draft is archived.")
    if draft.inventory_copy_id is None:
        raise HTTPException(status_code=422, detail="Draft missing inventory copy.")
    copy = session.get(InventoryCopy, draft.inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")

    prior_rows = session.exec(
        select(P78Listing).where(
            P78Listing.owner_user_id == owner_user_id,
            P78Listing.listing_draft_id == int(draft.id or 0),
        )
    ).all()
    prior = next((p for p in prior_rows if p.lifecycle_status in {"LISTED", "SOLD", "SHIPPED", "COMPLETED"}), None)
    if prior is not None:
        raise HTTPException(status_code=409, detail="Draft already published.")

    mode = (price_mode or "market").lower()
    asking = float(draft.market_price)
    if mode == "quick":
        asking = float(draft.quick_sale_price)
    elif mode == "premium":
        asking = float(draft.premium_price)

    qty = max(1, int(draft.suggested_sell_quantity))
    now = utc_now()
    listing = P78Listing(
        owner_user_id=owner_user_id,
        listing_draft_id=int(draft.id or 0),
        inventory_copy_id=int(copy.id or 0),
        lifecycle_status="LISTED",
        sync_state="ACTIVE",
        marketplace="EBAY",
        title=draft.title,
        description=draft.description,
        condition_label=draft.condition_suggested,
        asking_price=asking,
        quantity_listed=qty,
        listed_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(listing)
    session.flush()
    reserved = _reserve_copies(
        session,
        owner_user_id=owner_user_id,
        listing_id=int(listing.id or 0),
        anchor_copy=copy,
        quantity=qty,
    )
    listing.quantity_reserved = len(reserved)
    external_id = f"SIM-EBAY-{listing.id}"
    listing.external_listing_id = external_id
    listing.listing_url = f"https://www.ebay.com/itm/{external_id}"
    export_payload = {
        "marketplace": "EBAY",
        "title": draft.title,
        "description": draft.description,
        "condition": draft.condition_suggested,
        "price": asking,
        "quantity": qty,
        "shipping": draft.shipping_recommendation,
        "category": draft.category,
    }
    listing.export_payload_json = export_payload
    draft.status = "READY"
    session.add(draft)
    session.add(listing)
    session.flush()
    return P78ListingPublishRead(
        listing=_to_listing_read(listing),
        reserved_copy_ids=reserved,
        export_payload=export_payload,
    )


def _record_sale(
    session: Session,
    *,
    owner_user_id: int,
    listing: P78Listing,
    sold_price: float,
) -> P78SaleRecord:
    cost = 0.0
    qty = max(1, int(listing.quantity_listed))
    res_rows = list(
        session.exec(
            select(P78InventoryReservation).where(
                P78InventoryReservation.listing_id == int(listing.id or 0),
                P78InventoryReservation.active == True,  # noqa: E712
            )
        ).all()
    )
    for res in res_rows:
        c = session.get(InventoryCopy, res.inventory_copy_id)
        if c:
            cost += float(c.acquisition_cost or 0)
            c.hold_status = "sold"
            c.order_status = "sold"
            session.add(c)
    if cost <= 0 and listing.inventory_copy_id:
        c = session.get(InventoryCopy, listing.inventory_copy_id)
        if c:
            cost = float(c.acquisition_cost or 0) * qty

    fees = round(sold_price * EBAY_FEE_RATE, 2)
    shipping = DEFAULT_SHIPPING
    profit = round(sold_price - fees - shipping - cost, 2)
    roi = round((profit / cost * 100.0) if cost > 0 else 0.0, 1)
    now = utc_now()
    sale = P78SaleRecord(
        owner_user_id=owner_user_id,
        listing_id=int(listing.id or 0),
        marketplace=listing.marketplace,
        sale_price=sold_price,
        fees=fees,
        shipping_cost=shipping,
        cost_basis=round(cost, 2),
        profit=profit,
        roi_pct=roi,
        quantity_sold=qty,
        sold_at=now,
        metadata_json={"sync": "ebay"},
    )
    session.add(sale)
    session.flush()

    listing.lifecycle_status = "SOLD"
    listing.sync_state = "SOLD"
    listing.sold_price = sold_price
    listing.sold_at = now
    listing.fees = fees
    listing.shipping_cost = shipping
    listing.updated_at = now
    session.add(listing)
    _release_reservations(session, listing_id=int(listing.id or 0))

    meta = {}
    if listing.inventory_copy_id:
        c = session.get(InventoryCopy, listing.inventory_copy_id)
        if c:
            meta = copy_display_meta(session, c)
    from datetime import date

    outcome_row = P73RecommendationOutcome(
        owner_user_id=owner_user_id,
        recommendation_id=f"p78-sell-{listing.id}",
        inventory_copy_id=listing.inventory_copy_id,
        series=meta.get("series_name", ""),
        issue=meta.get("issue_number", ""),
        variant=meta.get("variant_label", ""),
        publisher=meta.get("publisher", ""),
        recommendation_type="SELL",
        recommendation_category="GENERAL",
        expected_profit=Decimal(str(round(float(listing.asking_price) - cost, 2))),
        actual_profit=Decimal(str(profit)),
        expected_roi_pct=Decimal(str(roi)),
        actual_roi_pct=Decimal(str(roi)),
        created_date=date.today(),
        current_status="SOLD",
        attribution_outcome="SOLD",
        attribution_accurate=profit > 0,
        source_table="p78_listing",
        source_row_id=int(listing.id or 0),
        notes="P78 realized sale",
        created_at=now,
        updated_at=now,
    )
    session.add(outcome_row)
    session.flush()
    sale.p73_outcome_id = int(outcome_row.id or 0)
    session.add(sale)
    return sale


def sync_listings(session: Session, *, owner_user_id: int) -> P78ListingSyncRead:
    rows = list(
        session.exec(
            select(P78Listing).where(
                P78Listing.owner_user_id == owner_user_id,
                P78Listing.sync_state == "ACTIVE",
            )
        ).all()
    )
    updated = 0
    sales = 0
    for listing in rows:
        if listing.sold_at is not None:
            continue
        sold_price = float(listing.asking_price or 0)
        if sold_price <= 0:
            continue
        _record_sale(session, owner_user_id=owner_user_id, listing=listing, sold_price=sold_price)
        listing.lifecycle_status = "COMPLETED"
        listing.completed_at = utc_now()
        session.add(listing)
        updated += 1
        sales += 1
    return P78ListingSyncRead(listings_checked=len(rows), listings_updated=updated, sales_recorded=sales)


def list_sales(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> P78SaleListResponse:
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    rows = list(
        session.exec(
            select(P78SaleRecord)
            .where(P78SaleRecord.owner_user_id == owner_user_id)
            .order_by(P78SaleRecord.sold_at.desc(), P78SaleRecord.id.desc())
        ).all()
    )
    page = rows[off : off + lim]
    items = [
        P78SaleRecordRead(
            id=int(s.id or 0),
            listing_id=int(s.listing_id),
            marketplace=s.marketplace,
            sale_price=float(s.sale_price),
            fees=float(s.fees),
            shipping_cost=float(s.shipping_cost),
            cost_basis=float(s.cost_basis),
            profit=float(s.profit),
            roi_pct=float(s.roi_pct),
            quantity_sold=int(s.quantity_sold),
            sold_at=s.sold_at,
            p73_outcome_id=s.p73_outcome_id,
        )
        for s in page
    ]
    return P78SaleListResponse(items=items, total_items=len(rows), limit=lim, offset=off)


def get_sale(session: Session, *, owner_user_id: int, sale_id: int) -> P78SaleRecordRead:
    row = session.get(P78SaleRecord, sale_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Sale not found.")
    return P78SaleRecordRead(
        id=int(row.id or 0),
        listing_id=int(row.listing_id),
        marketplace=row.marketplace,
        sale_price=float(row.sale_price),
        fees=float(row.fees),
        shipping_cost=float(row.shipping_cost),
        cost_basis=float(row.cost_basis),
        profit=float(row.profit),
        roi_pct=float(row.roi_pct),
        quantity_sold=int(row.quantity_sold),
        sold_at=row.sold_at,
        p73_outcome_id=row.p73_outcome_id,
    )
