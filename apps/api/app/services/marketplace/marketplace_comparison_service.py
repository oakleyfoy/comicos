"""P88-04 cross-marketplace comparison for buy opportunities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.listing_health_service import is_listing_displayable
from app.services.marketplace.marketplace_confidence_service import score_listing_confidence
from app.services.marketplace.marketplace_registry import marketplace_display_name


@dataclass(frozen=True)
class MarketplaceComparisonRow:
    marketplace: str
    marketplace_name: str
    price: float
    shipping: float
    overall_cost: float
    availability_status: str
    listing_confidence: str
    listing_count: int
    is_best: bool = False


@dataclass(frozen=True)
class MarketplaceComparisonResult:
    best_marketplace: str | None
    best_marketplace_name: str | None
    best_price: float | None
    best_total_cost: float | None
    savings_vs_highest: float | None
    rankings: tuple[MarketplaceComparisonRow, ...]


def _availability_for(row: P88MarketplaceListing) -> str:
    if row.availability_status:
        return row.availability_status
    if not row.is_active or row.health_status == "ENDED":
        return "ENDED"
    if row.health_status == "ACTIVE":
        return "ACTIVE"
    return "UNKNOWN"


def _best_per_marketplace(listings: list[P88MarketplaceListing]) -> dict[str, P88MarketplaceListing]:
    buckets: dict[str, list[P88MarketplaceListing]] = {}
    for row in listings:
        if not is_listing_displayable(row):
            continue
        buckets.setdefault(row.marketplace, []).append(row)
    best: dict[str, P88MarketplaceListing] = {}
    for code, rows in buckets.items():
        best[code] = min(rows, key=lambda item: (item.price + item.shipping_cost, item.id or 0))
    return best


def compare_listings(listings: list[P88MarketplaceListing]) -> MarketplaceComparisonResult:
    best_by_market = _best_per_marketplace(listings)
    if not best_by_market:
        return MarketplaceComparisonResult(
            best_marketplace=None,
            best_marketplace_name=None,
            best_price=None,
            best_total_cost=None,
            savings_vs_highest=None,
            rankings=(),
        )

    counts: dict[str, int] = {}
    for row in listings:
        if is_listing_displayable(row):
            counts[row.marketplace] = counts.get(row.marketplace, 0) + 1

    rows: list[MarketplaceComparisonRow] = []
    for code, row in best_by_market.items():
        total = round(row.price + row.shipping_cost, 2)
        rows.append(
            MarketplaceComparisonRow(
                marketplace=code,
                marketplace_name=marketplace_display_name(code),
                price=round(row.price, 2),
                shipping=round(row.shipping_cost, 2),
                overall_cost=total,
                availability_status=_availability_for(row),
                listing_confidence=row.listing_confidence or score_listing_confidence(row),
                listing_count=counts.get(code, 1),
            )
        )

    rows.sort(key=lambda item: (item.overall_cost, item.marketplace))
    best_row = rows[0]
    highest = max(item.overall_cost for item in rows)
    savings = round(highest - best_row.overall_cost, 2) if len(rows) > 1 else 0.0
    ranked = tuple(
        MarketplaceComparisonRow(
            marketplace=item.marketplace,
            marketplace_name=item.marketplace_name,
            price=item.price,
            shipping=item.shipping,
            overall_cost=item.overall_cost,
            availability_status=item.availability_status,
            listing_confidence=item.listing_confidence,
            listing_count=item.listing_count,
            is_best=item.marketplace == best_row.marketplace,
        )
        for item in rows
    )
    return MarketplaceComparisonResult(
        best_marketplace=best_row.marketplace,
        best_marketplace_name=best_row.marketplace_name,
        best_price=best_row.price,
        best_total_cost=best_row.overall_cost,
        savings_vs_highest=savings if savings > 0 else None,
        rankings=ranked,
    )


def compare_opportunity_listings(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_id: int,
) -> MarketplaceComparisonResult:
    rows = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.opportunity_id == opportunity_id)
    ).all()
    return compare_listings(list(rows))
