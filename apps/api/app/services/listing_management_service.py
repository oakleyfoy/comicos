"""P89-04 managed listing lifecycle (manual seller workflow)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy
from app.models.p89_listing_draft import P89ListingDraft
from app.models.p89_managed_listing import P89ManagedListing, utc_now
from app.services.listing_profit_service import apply_profit_to_listing
from app.services.storage_copy_meta import copy_display_meta

_ACTIVE_STATUSES = {"DRAFT", "ACTIVE"}
_TERMINAL_FROM_SOLD = {"ARCHIVED", "CANCELLED"}


def _load_history(row: P89ManagedListing) -> list[dict]:
    raw = row.status_history_json
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return list(parsed) if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    if isinstance(raw, list):
        return list(raw)
    return []


def listing_status_history(row: P89ManagedListing) -> list[dict]:
    return _load_history(row)


def _save_history(row: P89ManagedListing, history: list[dict]) -> None:
    row.status_history_json = history


def _append_status(row: P89ManagedListing, status: str, *, at: datetime | None = None) -> None:
    history = _load_history(row)
    stamp = at or utc_now()
    history.append({"status": status, "at": stamp.isoformat()})
    _save_history(row, history)


def _touch(row: P89ManagedListing) -> None:
    row.updated_at = utc_now()


def _require_listing(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = session.get(P89ManagedListing, listing_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Managed listing not found")
    return row


def _require_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> InventoryCopy:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or int(copy.user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    return copy


def listing_display_meta(session: Session, *, row: P89ManagedListing) -> dict[str, str]:
    copy = session.get(InventoryCopy, row.inventory_copy_id)
    meta = copy_display_meta(session, copy=copy) if copy else {}
    return {
        "comic_title": meta.get("display_title") or row.title or "Comic",
        "publisher": meta.get("publisher") or "",
        "issue_number": meta.get("issue_number") or "",
    }


def create_managed_listing(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    marketplace: str = "EBAY",
    title: str = "",
    asking_price: float | None = None,
    shipping_price: float | None = None,
    minimum_price: float | None = None,
    listing_url: str = "",
    external_listing_id: str = "",
    notes: str = "",
    listing_draft_id: int | None = None,
) -> P89ManagedListing:
    copy = _require_copy(session, owner_user_id=owner_user_id, inventory_copy_id=inventory_copy_id)
    if not title.strip():
        meta = copy_display_meta(session, copy=copy)
        title = meta.get("display_title") or "Comic listing"
    now = utc_now()
    row = P89ManagedListing(
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        listing_draft_id=listing_draft_id,
        marketplace=marketplace.upper(),
        title=title,
        asking_price=asking_price,
        shipping_price=shipping_price,
        minimum_price=minimum_price,
        listing_url=listing_url or "",
        external_listing_id=external_listing_id or "",
        status="DRAFT",
        notes=notes or "",
        created_at=now,
        updated_at=now,
    )
    _append_status(row, "DRAFT", at=now)
    session.add(row)
    session.flush()
    return row


def create_managed_listing_from_draft(
    session: Session,
    *,
    owner_user_id: int,
    listing_draft_id: int,
) -> P89ManagedListing:
    draft = session.get(P89ListingDraft, listing_draft_id)
    if draft is None or draft.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Listing draft not found")
    existing = session.exec(
        select(P89ManagedListing)
        .where(P89ManagedListing.owner_user_id == owner_user_id)
        .where(P89ManagedListing.listing_draft_id == listing_draft_id)
        .where(col(P89ManagedListing.status).notin_(["ARCHIVED", "CANCELLED"]))
        .limit(1)
    ).first()
    if existing is not None:
        return existing
    return create_managed_listing(
        session,
        owner_user_id=owner_user_id,
        inventory_copy_id=int(draft.inventory_copy_id),
        listing_draft_id=int(draft.id or 0),
        marketplace=draft.marketplace,
        title=draft.title,
        asking_price=draft.suggested_price,
        minimum_price=draft.minimum_price,
        notes="Created from listing draft.",
    )


def list_managed_listings(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    marketplace: str | None = None,
    inventory_copy_id: int | None = None,
    listed_from: datetime | None = None,
    listed_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[P89ManagedListing], int]:
    lim = min(max(limit, 1), 200)
    off = max(offset, 0)
    base = select(P89ManagedListing).where(P89ManagedListing.owner_user_id == owner_user_id)
    if status:
        base = base.where(P89ManagedListing.status == status.upper())
    if marketplace:
        base = base.where(P89ManagedListing.marketplace == marketplace.upper())
    if inventory_copy_id is not None:
        base = base.where(P89ManagedListing.inventory_copy_id == inventory_copy_id)
    if listed_from is not None:
        base = base.where(P89ManagedListing.listed_at >= listed_from)
    if listed_to is not None:
        base = base.where(P89ManagedListing.listed_at <= listed_to)
    count_q = select(func.count()).select_from(P89ManagedListing).where(P89ManagedListing.owner_user_id == owner_user_id)
    if status:
        count_q = count_q.where(P89ManagedListing.status == status.upper())
    if marketplace:
        count_q = count_q.where(P89ManagedListing.marketplace == marketplace.upper())
    if inventory_copy_id is not None:
        count_q = count_q.where(P89ManagedListing.inventory_copy_id == inventory_copy_id)
    if listed_from is not None:
        count_q = count_q.where(P89ManagedListing.listed_at >= listed_from)
    if listed_to is not None:
        count_q = count_q.where(P89ManagedListing.listed_at <= listed_to)
    total = int(session.exec(count_q).one() or 0)
    rows = list(
        session.exec(
            base.order_by(P89ManagedListing.updated_at.desc()).offset(off).limit(lim)
        ).all()
    )
    return rows, total


def update_managed_listing(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    fields: dict,
) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    allowed = {
        "listing_url",
        "external_listing_id",
        "asking_price",
        "shipping_price",
        "minimum_price",
        "notes",
        "title",
        "marketplace",
    }
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "marketplace" and value is not None:
            setattr(row, key, str(value).upper())
        else:
            setattr(row, key, value)
    _touch(row)
    session.add(row)
    return row


def mark_listing_active(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    if row.status not in {"DRAFT", "EXPIRED"}:
        raise HTTPException(status_code=400, detail=f"Cannot mark active from status {row.status}")
    now = utc_now()
    row.status = "ACTIVE"
    row.listed_at = row.listed_at or now
    row.expired_at = None
    _append_status(row, "ACTIVE", at=now)
    _touch(row)
    session.add(row)
    return row


def mark_listing_sold(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    sale_price: float,
    shipping_charged: float | None = None,
    marketplace_fees: float | None = None,
    shipping_cost: float | None = None,
    sold_at: datetime | None = None,
) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    if row.status in {"SOLD", "ARCHIVED", "CANCELLED"}:
        raise HTTPException(status_code=400, detail=f"Cannot mark sold from status {row.status}")
    now = sold_at or utc_now()
    row.status = "SOLD"
    row.sale_price = round(float(sale_price), 2)
    row.shipping_charged = round(float(shipping_charged or 0), 2)
    row.marketplace_fees = round(float(marketplace_fees or 0), 2)
    row.shipping_cost = round(float(shipping_cost or 0), 2)
    row.sold_at = now
    apply_profit_to_listing(session, listing=row)
    _append_status(row, "SOLD", at=now)
    _touch(row)
    session.add(row)
    return row


def mark_listing_expired(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    if row.status != "ACTIVE":
        raise HTTPException(status_code=400, detail=f"Cannot mark expired from status {row.status}")
    now = utc_now()
    row.status = "EXPIRED"
    row.expired_at = now
    _append_status(row, "EXPIRED", at=now)
    _touch(row)
    session.add(row)
    return row


def archive_managed_listing(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    now = utc_now()
    row.status = "ARCHIVED"
    row.archived_at = now
    _append_status(row, "ARCHIVED", at=now)
    _touch(row)
    session.add(row)
    return row


def cancel_managed_listing(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    if row.status == "SOLD":
        raise HTTPException(status_code=400, detail="Cannot cancel a sold listing")
    now = utc_now()
    row.status = "CANCELLED"
    _append_status(row, "CANCELLED", at=now)
    _touch(row)
    session.add(row)
    return row


def mark_inventory_sold_for_listing(session: Session, *, owner_user_id: int, listing_id: int) -> dict:
    row = _require_listing(session, owner_user_id=owner_user_id, listing_id=listing_id)
    if row.status != "SOLD":
        raise HTTPException(status_code=400, detail="Listing must be sold before updating inventory")
    copy = _require_copy(session, owner_user_id=owner_user_id, inventory_copy_id=int(row.inventory_copy_id))
    copy.order_status = "sold"
    copy.hold_status = "sold"
    session.add(copy)
    return {"inventory_copy_id": int(copy.id or 0), "order_status": copy.order_status}


def latest_managed_listing_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> P89ManagedListing | None:
    return session.exec(
        select(P89ManagedListing)
        .where(P89ManagedListing.owner_user_id == owner_user_id)
        .where(P89ManagedListing.inventory_copy_id == inventory_copy_id)
        .order_by(P89ManagedListing.updated_at.desc())
        .limit(1)
    ).first()


def build_portfolio_listing_summary(session: Session, *, owner_user_id: int) -> dict:
    rows = list(
        session.exec(select(P89ManagedListing).where(P89ManagedListing.owner_user_id == owner_user_id)).all()
    )
    sold = [r for r in rows if r.status == "SOLD"]
    active = [r for r in rows if r.status == "ACTIVE"]
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sold_month = [
        r for r in sold if r.sold_at is not None and r.sold_at.replace(tzinfo=timezone.utc) >= month_start
    ]
    realized = round(sum(float(r.sale_price or 0) for r in sold), 2)
    net_profit = round(sum(float(r.net_profit or 0) for r in sold if r.net_profit is not None), 2)
    active_value = round(sum(float(r.asking_price or 0) for r in active), 2)
    sold_month_profit = round(
        sum(float(r.net_profit or 0) for r in sold_month if r.net_profit is not None),
        2,
    )
    return {
        "realized_sales_total": realized,
        "total_net_profit": net_profit,
        "active_listing_value": active_value,
        "sold_this_month_count": len(sold_month),
        "sold_this_month_net_profit": sold_month_profit,
        "active_listings_count": len(active),
    }


def build_selling_activity_briefing(session: Session, *, owner_user_id: int) -> dict:
    summary = build_portfolio_listing_summary(session, owner_user_id=owner_user_id)
    sold_count = int(
        session.exec(
            select(func.count())
            .select_from(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "SOLD")
        ).one()
        or 0
    )
    expired_review = int(
        session.exec(
            select(func.count())
            .select_from(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "EXPIRED")
        ).one()
        or 0
    )
    return {
        "active_listings": summary["active_listings_count"],
        "sold_listings": sold_count,
        "net_profit": summary["total_net_profit"],
        "expired_needing_review": expired_review,
    }


def count_active_managed_listings(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "ACTIVE")
        ).one()
        or 0
    )


def count_sold_managed_listings_since(
    session: Session,
    *,
    owner_user_id: int,
    since: datetime,
) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "SOLD")
            .where(P89ManagedListing.sold_at >= since)
        ).one()
        or 0
    )
