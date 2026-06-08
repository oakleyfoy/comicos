"""P88-02 persist and link marketplace listings to buy opportunities."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing, utc_now
from app.services.marketplace.best_buy_service import recommend_best_buy
from app.services.marketplace.marketplace_comparison_service import compare_listings
from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing
from app.services.marketplace.listing_health_service import apply_health_to_listing, is_listing_displayable
from app.services.marketplace.marketplace_confidence_service import score_listing_confidence
from app.services.marketplace.marketplace_registry import marketplace_display_name
from app.services.marketplace.url_validation import validate_marketplace_url
from app.services.marketplace.verified_listing_service import (
    is_verified_marketplace_listing,
    pick_best_verified_listing,
    verified_listing_to_dict,
)


def _find_existing(
    session: Session,
    *,
    owner_user_id: int,
    marketplace: str,
    item_id: str,
) -> P88MarketplaceListing | None:
    return session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.marketplace == marketplace)
        .where(P88MarketplaceListing.item_id == item_id)
    ).first()


def upsert_listing_from_search(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_id: int | None,
    normalized: NormalizedMarketplaceListing,
) -> tuple[P88MarketplaceListing, bool]:
    """Returns (listing, created)."""
    now = utc_now()
    if not validate_marketplace_url(normalized.url).is_valid:
        raise ValueError("Invalid listing URL from marketplace search.")

    existing = _find_existing(
        session,
        owner_user_id=owner_user_id,
        marketplace=normalized.marketplace,
        item_id=normalized.item_id,
    )
    created = existing is None
    row = existing or P88MarketplaceListing(
        owner_user_id=owner_user_id,
        marketplace=normalized.marketplace,
        item_id=normalized.item_id,
    )
    if opportunity_id is not None:
        if row.opportunity_id is None:
            row.opportunity_id = opportunity_id
    if row.price and abs(row.price - normalized.price) > 0.009:
        row.previous_price = row.price
        row.price_last_changed_at = now
    row.title = normalized.title
    row.listing_url = normalized.url
    row.image_url = normalized.image_url
    row.price = normalized.price
    row.shipping_cost = normalized.shipping
    row.condition = normalized.condition
    row.seller_name = normalized.seller
    row.listing_type = normalized.listing_type
    row.end_time = normalized.end_time
    row.is_active = True
    row.marketplace_name = marketplace_display_name(normalized.marketplace)
    row.currency = "USD"
    row.last_verified_at = now
    row.updated_at = now
    apply_health_to_listing(row, now=now)
    row.availability_status = "ACTIVE" if row.health_status == "ACTIVE" else "UNKNOWN"
    row.listing_confidence = score_listing_confidence(row)
    session.add(row)
    session.flush()
    return row, created


def pick_best_listing(listings: list[P88MarketplaceListing]) -> P88MarketplaceListing | None:
    best_verified = pick_best_verified_listing(listings)
    if best_verified is not None:
        return best_verified
    active = [row for row in listings if is_listing_displayable(row)]
    if not active:
        return None
    return min(active, key=lambda row: (row.price + row.shipping_cost, row.id or 0))


def sync_opportunity_best_listing(
    session: Session,
    *,
    opportunity: MarketplaceAcquisitionOpportunity,
) -> None:
    assert opportunity.id is not None
    listings = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.opportunity_id == opportunity.id)
        .where(P88MarketplaceListing.owner_user_id == opportunity.owner_user_id)
    ).all()
    best = pick_best_listing(listings)
    now = utc_now()
    if best is None:
        opportunity.best_listing_id = None
        opportunity.updated_at = now
        session.add(opportunity)
        return
    opportunity.best_listing_id = best.id
    total = best.price + best.shipping_cost
    opportunity.listing_url = best.listing_url
    opportunity.external_listing_id = best.item_id
    opportunity.marketplace = best.marketplace
    if total > 0:
        opportunity.asking_price = round(total, 2)
    opportunity.updated_at = now
    session.add(opportunity)


def listing_summary_for_opportunity(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_id: int,
) -> dict[str, object]:
    listings = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.opportunity_id == opportunity_id)
    ).all()
    displayable = [row for row in listings if is_listing_displayable(row)]
    verified = [row for row in listings if is_verified_marketplace_listing(row)]
    best_verified = pick_best_verified_listing(listings)
    best = best_verified or pick_best_listing(displayable)
    comparison = compare_listings(displayable)
    best_buy = recommend_best_buy(displayable)
    best_marketplace_name = comparison.best_marketplace_name
    if best_marketplace_name is None and best is not None:
        best_marketplace_name = marketplace_display_name(best.marketplace)
    best_total_cost = round(best.price + best.shipping_cost, 2) if best_verified else None
    return {
        "active_listing_count": len(displayable),
        "verified_listing_count": len(verified),
        "best_active_price": round(best.price + best.shipping_cost, 2) if best else None,
        "best_total_cost": best_total_cost,
        "listing_marketplace": best.marketplace if best else None,
        "best_listing_id": best.id if best else None,
        "has_verified_listings": bool(best_verified),
        "best_verified_listing": verified_listing_to_dict(best_verified) if best_verified else None,
        "best_marketplace": comparison.best_marketplace,
        "best_marketplace_name": best_marketplace_name,
        "best_market_price": comparison.best_price,
        "savings_vs_highest": comparison.savings_vs_highest,
        "best_buy_reason": best_buy.reason,
        "marketplace_count": len({row.marketplace for row in displayable}),
    }
