"""P88-04 listing confidence scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.adapters.base import ListingConfidence
from app.services.marketplace.marketplace_registry import marketplace_definition

_FRESH_DAYS = 7


def _freshness_score(last_verified_at: datetime | None) -> float:
    if last_verified_at is None:
        return 0.2
    if last_verified_at.tzinfo is None:
        last_verified_at = last_verified_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last_verified_at
    if age <= timedelta(days=1):
        return 1.0
    if age <= timedelta(days=_FRESH_DAYS):
        return 0.75
    if age <= timedelta(days=30):
        return 0.45
    return 0.15


def _completeness_score(row: P88MarketplaceListing) -> float:
    fields = [
        row.title,
        row.listing_url,
        row.condition,
        row.seller_name,
    ]
    filled = sum(1 for value in fields if str(value or "").strip())
    price_ok = row.price > 0
    return min(1.0, (filled / 4.0) * 0.85 + (0.15 if price_ok else 0.0))


def score_listing_confidence(row: P88MarketplaceListing) -> ListingConfidence:
    definition = marketplace_definition(row.marketplace)
    source = 1.0 if definition.supports_search else 0.35
    refresh_ok = 1.0 if row.last_verified_at else 0.3
    if row.health_status == "ENDED" or not row.is_active:
        return "LOW"
    composite = (
        source * 0.35
        + _freshness_score(row.last_verified_at) * 0.35
        + _completeness_score(row) * 0.2
        + refresh_ok * 0.1
    )
    if composite >= 0.72:
        return "HIGH"
    if composite >= 0.45:
        return "MEDIUM"
    return "LOW"


def score_marketplace_confidence(
    *,
    marketplace: str,
    listing_count: int,
    last_verified_at: datetime | None,
    search_supported: bool,
) -> ListingConfidence:
    if listing_count <= 0 and not search_supported:
        return "LOW"
    freshness = _freshness_score(last_verified_at)
    volume = min(1.0, listing_count / 5.0)
    source = 1.0 if search_supported else 0.4
    composite = source * 0.4 + freshness * 0.35 + volume * 0.25
    if composite >= 0.7:
        return "HIGH"
    if composite >= 0.45:
        return "MEDIUM"
    return "LOW"
