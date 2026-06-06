"""P78-02 selling analytics and dashboard."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.p78_marketplace_lifecycle import P78Listing, P78SaleRecord, P78SellingAnalyticsSnapshot
from app.models.p78_sell_workflow import P78ListingDraft
from app.schemas.p78_marketplace import P78SellingAnalyticsRead, P78SellingDashboardRead
from app.services.p78_listing_lifecycle_service import _to_listing_read, list_listings, list_sales


def build_selling_analytics(session: Session, *, owner_user_id: int, persist: bool = True) -> P78SellingAnalyticsRead:
    sales = list(
        session.exec(select(P78SaleRecord).where(P78SaleRecord.owner_user_id == owner_user_id)).all()
    )
    listings = list(session.exec(select(P78Listing).where(P78Listing.owner_user_id == owner_user_id)).all())
    drafts = list(session.exec(select(P78ListingDraft).where(P78ListingDraft.owner_user_id == owner_user_id)).all())
    revenue = sum(float(s.sale_price) for s in sales)
    profit = sum(float(s.profit) for s in sales)
    cost = sum(float(s.cost_basis) for s in sales)
    roi = round((profit / cost * 100.0) if cost > 0 else 0.0, 1)
    sold_count = len(sales)
    created = len(listings) + len([d for d in drafts if d.status != "ARCHIVED"])
    conversion = round(100.0 * sold_count / max(1, len(listings)), 1) if listings else 0.0
    days: list[float] = []
    for listing in listings:
        if listing.listed_at and listing.sold_at:
            delta = (listing.sold_at - listing.listed_at).total_seconds() / 86400.0
            days.append(delta)
    avg_days = round(sum(days) / len(days), 1) if days else None
    accurate = sum(1 for s in sales if s.profit > 0)
    acc_pct = round(100.0 * accurate / max(1, sold_count), 1) if sold_count else None

    snap_id = None
    metrics = {
        "revenue": round(revenue, 2),
        "profit": round(profit, 2),
        "roi_pct": roi,
        "listings_created": created,
        "listings_sold": sold_count,
        "sell_conversion_rate_pct": conversion,
        "average_days_to_sell": avg_days,
        "sell_recommendation_accuracy_pct": acc_pct,
    }
    if persist:
        row = P78SellingAnalyticsSnapshot(
            owner_user_id=owner_user_id,
            snapshot_date=date.today(),
            metrics_json=metrics,
        )
        session.add(row)
        session.flush()
        snap_id = int(row.id or 0)

    return P78SellingAnalyticsRead(
        revenue=metrics["revenue"],
        profit=metrics["profit"],
        roi_pct=roi,
        listings_created=created,
        listings_sold=sold_count,
        sell_conversion_rate_pct=conversion,
        average_days_to_sell=avg_days,
        sell_recommendation_accuracy_pct=acc_pct,
        snapshot_id=snap_id,
    )


def build_selling_dashboard(session: Session, *, owner_user_id: int) -> P78SellingDashboardRead:
    analytics = build_selling_analytics(session, owner_user_id=owner_user_id, persist=True)
    active = list_listings(session, owner_user_id=owner_user_id, lifecycle_status="LISTED", limit=20, offset=0)
    sold = list_listings(session, owner_user_id=owner_user_id, lifecycle_status="COMPLETED", limit=20, offset=0)
    if not sold.items:
        sold = list_listings(session, owner_user_id=owner_user_id, lifecycle_status="SOLD", limit=20, offset=0)
    all_drafts = list(session.exec(select(P78ListingDraft).where(P78ListingDraft.owner_user_id == owner_user_id)).all())
    drafts = [d for d in all_drafts if d.status in {"DRAFT", "READY", "CANDIDATE"}]
    draft_views = [
        {"id": int(d.id or 0), "title": d.title, "status": d.status, "market_price": d.market_price}
        for d in drafts[:20]
    ]
    recent = list_sales(session, owner_user_id=owner_user_id, limit=10, offset=0)
    return P78SellingDashboardRead(
        analytics=analytics,
        active_listings=active.items,
        sold_listings=sold.items,
        draft_listings=draft_views,
        recent_sales=recent.items,
    )
