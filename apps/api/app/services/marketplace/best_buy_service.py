"""P88-04 best buy recommendation across marketplaces."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.listing_health_service import is_listing_displayable
from app.services.marketplace.marketplace_comparison_service import (
    MarketplaceComparisonResult,
    compare_listings,
)
from app.services.marketplace.marketplace_confidence_service import score_listing_confidence
from app.services.marketplace.marketplace_registry import marketplace_display_name


@dataclass(frozen=True)
class BestBuyRecommendation:
    marketplace: str | None
    marketplace_name: str | None
    price: float | None
    shipping: float | None
    total_cost: float | None
    reason: str
    listing_confidence: str | None = None


def _pick_most_trusted(listings: list[P88MarketplaceListing]) -> P88MarketplaceListing | None:
    active = [row for row in listings if is_listing_displayable(row)]
    if not active:
        return None

    def trust_key(row: P88MarketplaceListing) -> tuple[int, float, int]:
        confidence = score_listing_confidence(row)
        rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(confidence, 3)
        return (rank, row.price + row.shipping_cost, row.id or 0)

    return min(active, key=trust_key)


def recommend_best_buy(listings: list[P88MarketplaceListing]) -> BestBuyRecommendation:
    comparison: MarketplaceComparisonResult = compare_listings(listings)
    if comparison.best_marketplace is None or comparison.best_total_cost is None:
        return BestBuyRecommendation(
            marketplace=None,
            marketplace_name=None,
            price=None,
            shipping=None,
            total_cost=None,
            reason="No active marketplace listings available.",
        )

    best_row = comparison.rankings[0]
    return BestBuyRecommendation(
        marketplace=best_row.marketplace,
        marketplace_name=best_row.marketplace_name,
        price=best_row.price,
        shipping=best_row.shipping,
        total_cost=best_row.overall_cost,
        reason="Lowest total cost available.",
        listing_confidence=best_row.listing_confidence,
    )


def recommend_most_trusted(listings: list[P88MarketplaceListing]) -> BestBuyRecommendation:
    row = _pick_most_trusted(listings)
    if row is None:
        return BestBuyRecommendation(
            marketplace=None,
            marketplace_name=None,
            price=None,
            shipping=None,
            total_cost=None,
            reason="No trusted marketplace listing available.",
        )
    confidence = score_listing_confidence(row)
    total = round(row.price + row.shipping_cost, 2)
    return BestBuyRecommendation(
        marketplace=row.marketplace,
        marketplace_name=marketplace_display_name(row.marketplace),
        price=round(row.price, 2),
        shipping=round(row.shipping_cost, 2),
        total_cost=total,
        reason="Most trusted marketplace listing.",
        listing_confidence=confidence,
    )
