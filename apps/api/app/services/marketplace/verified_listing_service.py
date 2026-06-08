"""Resolve safe, verified P88 marketplace listings for buy actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.listing_health_service import is_listing_displayable
from app.services.marketplace.marketplace_registry import marketplace_display_name
from app.services.p82_listing_url_safety import is_safe_marketplace_listing_url


def is_verified_marketplace_listing(listing: P88MarketplaceListing) -> bool:
    if not is_listing_displayable(listing):
        return False
    if listing.health_status != "ACTIVE":
        return False
    if float(listing.price or 0) <= 0:
        return False
    return is_safe_marketplace_listing_url(
        listing_url=listing.listing_url,
        external_listing_id=listing.item_id,
    )


def pick_best_verified_listing(listings: list[P88MarketplaceListing]) -> P88MarketplaceListing | None:
    verified = [row for row in listings if is_verified_marketplace_listing(row)]
    if not verified:
        return None
    return min(verified, key=lambda row: (row.price + row.shipping_cost, row.id or 0))


def verified_listing_to_dict(listing: P88MarketplaceListing) -> dict[str, Any]:
    total = round(float(listing.price) + float(listing.shipping_cost or 0), 2)
    verified_at: datetime | None = listing.last_verified_at
    return {
        "marketplace": listing.marketplace,
        "marketplace_name": listing.marketplace_name or marketplace_display_name(listing.marketplace),
        "listing_url": listing.listing_url,
        "price": round(float(listing.price), 2),
        "shipping": round(float(listing.shipping_cost or 0), 2),
        "total_cost": total,
        "seller": listing.seller_name or "",
        "condition": listing.condition or "",
        "last_verified_at": verified_at.isoformat() if verified_at else None,
        "confidence": listing.listing_confidence or "MEDIUM",
    }
