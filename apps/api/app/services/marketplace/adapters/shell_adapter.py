"""P88-04 placeholder adapters for marketplaces without official APIs."""

from __future__ import annotations

from app.core.config import Settings
from app.services.marketplace.adapters.base import (
    AdapterOperationResult,
    MarketplaceAdapter,
    UnifiedMarketplaceListing,
    not_supported_result,
)
from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing
from app.services.marketplace.marketplace_registry import marketplace_display_name


class ShellMarketplaceAdapter(MarketplaceAdapter):
    def __init__(self, marketplace_code: str) -> None:
        self.marketplace_code = marketplace_code

    def search(
        self,
        *,
        query: str,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        limit: int = 15,
        settings: Settings | None = None,
    ) -> AdapterOperationResult:
        return not_supported_result()

    def lookup(self, *, item_id: str, settings: Settings | None = None) -> AdapterOperationResult:
        return not_supported_result()

    def refresh(self, *, item_id: str, settings: Settings | None = None) -> AdapterOperationResult:
        return not_supported_result()

    def normalize(self, listing: NormalizedMarketplaceListing) -> UnifiedMarketplaceListing:
        total = round(float(listing.price) + float(listing.shipping), 2)
        return UnifiedMarketplaceListing(
            marketplace=self.marketplace_code,
            marketplace_name=marketplace_display_name(self.marketplace_code),
            item_id=listing.item_id,
            title=listing.title,
            url=listing.url,
            price=float(listing.price),
            shipping=float(listing.shipping),
            overall_cost=total,
            condition=listing.condition,
            seller=listing.seller,
            listing_type=listing.listing_type,
            end_time=listing.end_time,
            image_url=listing.image_url,
            availability_status="UNKNOWN",
            listing_confidence="LOW",
            currency="USD",
        )
