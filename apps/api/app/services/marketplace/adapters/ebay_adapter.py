"""P88-04 eBay marketplace adapter (Browse API)."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.marketplace.adapters.base import (
    AdapterOperationResult,
    MarketplaceAdapter,
    UnifiedMarketplaceListing,
)
from app.services.marketplace.ebay_search_service import (
    EbayLiveSearchApiError,
    EbayLiveSearchConfigurationError,
    NormalizedMarketplaceListing,
    fetch_item_by_id,
    search_comics,
)
from app.services.marketplace.marketplace_registry import marketplace_display_name


class EbayMarketplaceAdapter(MarketplaceAdapter):
    marketplace_code = "EBAY"

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
        resolved = settings or get_settings()
        try:
            rows = search_comics(
                title=query,
                series=series,
                issue_number=issue_number,
                publisher=publisher,
                limit=limit,
                settings=resolved,
            )
        except (EbayLiveSearchConfigurationError, EbayLiveSearchApiError, ValueError) as exc:
            return AdapterOperationResult(status="ERROR", error=str(exc))
        return AdapterOperationResult(status="OK", listings=tuple(rows))

    def lookup(self, *, item_id: str, settings: Settings | None = None) -> AdapterOperationResult:
        resolved = settings or get_settings()
        try:
            row = fetch_item_by_id(item_id=item_id, settings=resolved)
        except (EbayLiveSearchConfigurationError, EbayLiveSearchApiError, ValueError) as exc:
            return AdapterOperationResult(status="ERROR", error=str(exc))
        if row is None:
            return AdapterOperationResult(status="ERROR", error="Listing not found.")
        return AdapterOperationResult(status="OK", listing=row)

    def refresh(self, *, item_id: str, settings: Settings | None = None) -> AdapterOperationResult:
        return self.lookup(item_id=item_id, settings=settings)

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
            availability_status="ACTIVE",
            listing_confidence="HIGH",
            currency="USD",
        )
