"""P88-02 refresh stored marketplace listings from eBay Browse API."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models.p88_marketplace_listing import P88MarketplaceListing, utc_now
from app.services.marketplace.ebay_search_service import fetch_item_by_id
from app.services.marketplace.listing_health_service import apply_health_to_listing


def refresh_marketplace_listing(
    session: Session,
    *,
    listing: P88MarketplaceListing,
    settings: Settings | None = None,
) -> P88MarketplaceListing:
    resolved = settings or get_settings()
    now = utc_now()
    fetched = fetch_item_by_id(item_id=listing.item_id, settings=resolved)
    if fetched is None:
        listing.is_active = False
        listing.health_status = "ENDED"
        listing.last_verified_at = now
        listing.updated_at = now
        session.add(listing)
        return listing

    if listing.price and abs(listing.price - fetched.price) > 0.009:
        listing.previous_price = listing.price
    listing.title = fetched.title or listing.title
    listing.listing_url = fetched.url or listing.listing_url
    listing.image_url = fetched.image_url or listing.image_url
    listing.price = fetched.price
    listing.shipping_cost = fetched.shipping
    listing.condition = fetched.condition or listing.condition
    listing.seller_name = fetched.seller or listing.seller_name
    listing.listing_type = fetched.listing_type or listing.listing_type
    listing.end_time = fetched.end_time or listing.end_time
    listing.is_active = True
    listing.last_verified_at = now
    listing.updated_at = now
    apply_health_to_listing(listing, now=now)
    session.add(listing)
    return listing


def refresh_listings_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    settings: Settings | None = None,
) -> tuple[int, int, int]:
    """Returns (refreshed, ended, invalid)."""
    rows = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.is_active == True)  # noqa: E712
        .order_by(P88MarketplaceListing.id.desc())
        .limit(limit)
    ).all()
    refreshed = ended = invalid = 0
    for row in rows:
        before = row.health_status
        refresh_marketplace_listing(session, listing=row, settings=settings)
        if row.health_status == "ENDED":
            ended += 1
        elif row.health_status == "INVALID":
            invalid += 1
        elif row.health_status == "ACTIVE" or before != row.health_status:
            refreshed += 1
    return refreshed, ended, invalid
