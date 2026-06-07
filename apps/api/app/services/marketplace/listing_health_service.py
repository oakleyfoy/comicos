"""P88-02 marketplace listing health (ACTIVE, ENDED, STALE, INVALID)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.p88_marketplace_listing import P88MarketplaceListing, utc_now
from app.services.marketplace.url_validation import validate_marketplace_url

STALE_AFTER = timedelta(days=7)


def evaluate_listing_health(listing: P88MarketplaceListing, *, now: datetime | None = None) -> str:
    """Return health_status without mutating the listing."""
    current = now or utc_now()
    url_ok = validate_marketplace_url(listing.listing_url).is_valid
    if not url_ok or not (listing.item_id or "").strip():
        return "INVALID"
    if not listing.is_active or listing.health_status == "ENDED":
        return "ENDED"
    if listing.end_time and listing.end_time < current:
        return "ENDED"
    verified = listing.last_verified_at
    if verified is None:
        return "STALE"
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=timezone.utc)
    if current - verified > STALE_AFTER:
        return "STALE"
    return "ACTIVE"


def apply_health_to_listing(listing: P88MarketplaceListing, *, now: datetime | None = None) -> str:
    status = evaluate_listing_health(listing, now=now)
    listing.health_status = status
    if status == "ENDED":
        listing.is_active = False
    elif status == "ACTIVE":
        listing.is_active = True
    return status


def listing_health_badges(listing: P88MarketplaceListing, *, now: datetime | None = None) -> list[str]:
    current = now or utc_now()
    badges: list[str] = []
    verified = listing.last_verified_at
    if verified:
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        if verified.date() == current.date():
            badges.append("Verified Today")
        elif current - verified <= STALE_AFTER:
            badges.append("Verified This Week")
    if listing.health_status == "ENDED" or (listing.end_time and listing.end_time < current):
        badges.append("Listing Ended")
    if listing.previous_price is not None and abs(listing.previous_price - listing.price) > 0.009:
        badges.append("Price Changed")
    return badges


def is_listing_displayable(listing: P88MarketplaceListing) -> bool:
    """Active listings with valid URLs only."""
    if not listing.is_active:
        return False
    if listing.health_status in {"ENDED", "INVALID"}:
        return False
    return validate_marketplace_url(listing.listing_url).is_valid
