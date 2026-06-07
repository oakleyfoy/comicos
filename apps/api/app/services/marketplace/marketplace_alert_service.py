"""P88-03 marketplace alert reads and updates."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.models.p88_marketplace_monitoring import MarketplaceAlert, utc_now
from app.schemas.p88_marketplace_monitoring import MarketplaceAlertListResponse, MarketplaceAlertRead, MarketplaceAlertUpdatePayload


def _to_read(
    row: MarketplaceAlert,
    *,
    listing: P88MarketplaceListing | None = None,
    opportunity: MarketplaceAcquisitionOpportunity | None = None,
) -> MarketplaceAlertRead:
    return MarketplaceAlertRead(
        id=int(row.id or 0),
        saved_search_id=row.saved_search_id,
        opportunity_id=row.opportunity_id,
        listing_id=row.listing_id,
        alert_type=row.alert_type,
        title=row.title,
        message=row.message,
        severity=row.severity,
        status=row.status,
        marketplace=listing.marketplace if listing else None,
        listing_url=listing.listing_url if listing else None,
        external_item_id=listing.item_id if listing else None,
        price=float(listing.price) if listing else None,
        shipping_cost=float(listing.shipping_cost) if listing else None,
        estimated_fmv=float(opportunity.estimated_fmv) if opportunity else None,
        created_at=row.created_at,
        acknowledged_at=row.acknowledged_at,
    )


def list_marketplace_alerts(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketplaceAlertListResponse:
    stmt = select(MarketplaceAlert).where(MarketplaceAlert.owner_user_id == owner_user_id)
    if status:
        stmt = stmt.where(MarketplaceAlert.status == status.strip().upper())
    rows = list(session.exec(stmt.order_by(MarketplaceAlert.created_at.desc())).all())
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page: list[MarketplaceAlertRead] = []
    for row in rows[off : off + lim]:
        listing = session.get(P88MarketplaceListing, row.listing_id) if row.listing_id else None
        opp = session.get(MarketplaceAcquisitionOpportunity, row.opportunity_id) if row.opportunity_id else None
        page.append(_to_read(row, listing=listing, opportunity=opp))
    return MarketplaceAlertListResponse(items=page, total_items=len(rows), limit=lim, offset=off)


def update_marketplace_alert(
    session: Session,
    *,
    owner_user_id: int,
    alert_id: int,
    payload: MarketplaceAlertUpdatePayload,
) -> MarketplaceAlertRead:
    row = session.get(MarketplaceAlert, alert_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Alert not found.")
    row.status = payload.status
    if payload.status == "ACKNOWLEDGED":
        row.acknowledged_at = utc_now()
    session.add(row)
    session.flush()
    listing = session.get(P88MarketplaceListing, row.listing_id) if row.listing_id else None
    opp = session.get(MarketplaceAcquisitionOpportunity, row.opportunity_id) if row.opportunity_id else None
    return _to_read(row, listing=listing, opportunity=opp)


def count_new_marketplace_alerts(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.status == "NEW")
        ).one()
        or 0
    )
