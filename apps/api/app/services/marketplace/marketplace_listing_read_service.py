"""P88-02 marketplace listing reads and admin metrics."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.p88_marketplace_listing import MarketplaceSearchRun, P88MarketplaceListing
from app.schemas.p88_marketplace_live import (
    MarketplaceListingListResponse,
    MarketplaceListingRead,
    MarketplaceSearchDashboardRead,
)
from app.services.marketplace.listing_health_service import is_listing_displayable, listing_health_badges
from app.services.marketplace.marketplace_registry import marketplace_display_name


def _to_listing_read(row: P88MarketplaceListing) -> MarketplaceListingRead:
    return MarketplaceListingRead(
        id=int(row.id or 0),
        marketplace=row.marketplace,
        item_id=row.item_id,
        title=row.title,
        listing_url=row.listing_url,
        image_url=row.image_url,
        price=float(row.price),
        shipping_cost=float(row.shipping_cost),
        condition=row.condition,
        seller_name=row.seller_name,
        listing_type=row.listing_type,
        end_time=row.end_time,
        is_active=bool(row.is_active),
        health_status=row.health_status,
        health_badges=listing_health_badges(row),
        marketplace_name=row.marketplace_name or marketplace_display_name(row.marketplace),
        availability_status=row.availability_status or "UNKNOWN",
        listing_confidence=row.listing_confidence or "MEDIUM",
        currency=row.currency or "USD",
        price_last_changed_at=row.price_last_changed_at,
        last_verified_at=row.last_verified_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_opportunity_listings(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_id: int,
    include_inactive: bool = False,
) -> MarketplaceListingListResponse:
    query = (
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.opportunity_id == opportunity_id)
        .order_by(P88MarketplaceListing.price.asc(), P88MarketplaceListing.id.asc())
    )
    rows = session.exec(query).all()
    items: list[MarketplaceListingRead] = []
    for row in rows:
        if not include_inactive and not is_listing_displayable(row):
            continue
        items.append(_to_listing_read(row))
    return MarketplaceListingListResponse(items=items, total_items=len(items), limit=200, offset=0)


def marketplace_search_dashboard(
    session: Session,
    *,
    owner_user_id: int | None = None,
    recent_limit: int = 25,
) -> MarketplaceSearchDashboardRead:
    run_query = select(MarketplaceSearchRun).order_by(MarketplaceSearchRun.id.desc()).limit(recent_limit)
    listing_query = select(P88MarketplaceListing)
    if owner_user_id is not None:
        run_query = run_query.where(MarketplaceSearchRun.owner_user_id == owner_user_id)
        listing_query = listing_query.where(P88MarketplaceListing.owner_user_id == owner_user_id)

    runs = session.exec(run_query).all()
    total_runs = session.exec(select(func.count()).select_from(MarketplaceSearchRun)).one()
    if isinstance(total_runs, tuple):
        total_runs = total_runs[0]
    searches_run = sum(r.searches_run for r in runs)
    failed = sum(r.failed_searches for r in runs)
    success_rate = 100.0
    if searches_run > 0:
        success_rate = round(max(0.0, (searches_run - failed) / searches_run * 100.0), 1)

    listings_found_total = sum(r.listings_found for r in runs)
    new_total = sum(r.new_listings for r in runs)
    updated_total = sum(r.updated_listings for r in runs)
    failed_total = sum(r.failed_searches for r in runs)

    all_listings = session.exec(listing_query).all()
    active = sum(1 for row in all_listings if row.is_active and row.health_status == "ACTIVE")
    ended = sum(1 for row in all_listings if row.health_status == "ENDED" or not row.is_active)

    recent_errors: list[str] = []
    for run in runs:
        for err in run.errors_json or []:
            if isinstance(err, str):
                recent_errors.append(err)
        if len(recent_errors) >= 15:
            break

    return MarketplaceSearchDashboardRead(
        total_search_runs=int(total_runs),
        recent_searches_run=searches_run,
        success_rate_percent=success_rate,
        listings_found_total=listings_found_total,
        new_listings_total=new_total,
        updated_listings_total=updated_total,
        failed_searches_total=failed_total,
        active_listings=active,
        ended_listings=ended,
        recent_errors=recent_errors[:15],
    )
