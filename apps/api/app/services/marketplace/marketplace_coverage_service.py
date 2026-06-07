"""P88-04 marketplace coverage reporting."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.p88_marketplace_listing import MarketplaceSearchRun, P88MarketplaceListing
from app.schemas.p88_marketplace_comparison import MarketplaceCoverageRead, MarketplaceCoverageRow
from app.services.marketplace.marketplace_registry import (
    MARKETPLACE_REGISTRY,
    list_supported_marketplace_codes,
    marketplace_definition,
)


def build_marketplace_coverage(session: Session, *, owner_user_id: int | None = None) -> MarketplaceCoverageRead:
    listing_query = select(
        P88MarketplaceListing.marketplace,
        func.count(P88MarketplaceListing.id),
    ).group_by(P88MarketplaceListing.marketplace)
    if owner_user_id is not None:
        listing_query = listing_query.where(P88MarketplaceListing.owner_user_id == owner_user_id)
    listing_counts = {str(code): int(count) for code, count in session.exec(listing_query).all()}

    run_query = select(MarketplaceSearchRun).order_by(MarketplaceSearchRun.id.desc()).limit(50)
    if owner_user_id is not None:
        run_query = run_query.where(MarketplaceSearchRun.owner_user_id == owner_user_id)
    runs = session.exec(run_query).all()
    searches_run = sum(r.searches_run for r in runs)
    failed = sum(r.failed_searches for r in runs)
    success_rate = 100.0
    if searches_run > 0:
        success_rate = round(max(0.0, (searches_run - failed) / searches_run * 100.0), 1)

    rows: list[MarketplaceCoverageRow] = []
    supported: list[str] = []
    unsupported: list[str] = []
    for code in list_supported_marketplace_codes():
        definition = marketplace_definition(code)
        count = listing_counts.get(code, 0)
        rows.append(
            MarketplaceCoverageRow(
                marketplace=code,
                marketplace_name=definition.display_name,
                listing_count=count,
                supports_search=definition.supports_search,
                supports_listing_lookup=definition.supports_listing_lookup,
                supports_price_tracking=definition.supports_price_tracking,
                supports_refresh=definition.supports_refresh,
            )
        )
        if definition.supports_search:
            supported.append(definition.display_name)
        else:
            unsupported.append(definition.display_name)

    return MarketplaceCoverageRead(
        listings_by_marketplace=rows,
        search_success_rate_percent=success_rate,
        supported_marketplaces=supported,
        unsupported_marketplaces=unsupported,
        total_listings=sum(listing_counts.values()),
        registry_marketplace_count=len(MARKETPLACE_REGISTRY),
    )
