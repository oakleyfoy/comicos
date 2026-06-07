"""P88-04 marketplace comparison API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketplaceComparisonRowRead(BaseModel):
    marketplace: str
    marketplace_name: str
    price: float | None = None
    shipping: float | None = None
    overall_cost: float | None = None
    availability_status: str
    listing_confidence: str
    listing_count: int = 0
    is_best: bool = False


class MarketplaceComparisonRead(BaseModel):
    best_marketplace: str | None = None
    best_marketplace_name: str | None = None
    best_price: float | None = None
    best_total_cost: float | None = None
    savings_vs_highest: float | None = None
    rankings: list[MarketplaceComparisonRowRead] = Field(default_factory=list)


class BestBuyRecommendationRead(BaseModel):
    marketplace: str | None = None
    marketplace_name: str | None = None
    price: float | None = None
    shipping: float | None = None
    total_cost: float | None = None
    reason: str
    listing_confidence: str | None = None


class MarketplaceCoverageRow(BaseModel):
    marketplace: str
    marketplace_name: str
    listing_count: int
    supports_search: bool
    supports_listing_lookup: bool
    supports_price_tracking: bool
    supports_refresh: bool


class MarketplaceCoverageRead(BaseModel):
    listings_by_marketplace: list[MarketplaceCoverageRow] = Field(default_factory=list)
    search_success_rate_percent: float = 100.0
    supported_marketplaces: list[str] = Field(default_factory=list)
    unsupported_marketplaces: list[str] = Field(default_factory=list)
    total_listings: int = 0
    registry_marketplace_count: int = 0


class MarketplaceDiagnosticsRow(BaseModel):
    marketplace: str
    marketplace_name: str
    adapter_status: str
    marketplace_support_status: str
    supports_search: bool
    supports_listing_lookup: bool
    supports_price_tracking: bool
    supports_refresh: bool
    listing_count: int
    last_successful_search: datetime | None = None
    last_successful_refresh: datetime | None = None


class MarketplaceDiagnosticsRead(BaseModel):
    adapters: list[MarketplaceDiagnosticsRow] = Field(default_factory=list)
    recent_errors: list[str] = Field(default_factory=list)
    last_search_run_at: datetime | None = None


class MarketplaceRegistryEntryRead(BaseModel):
    code: str
    display_name: str
    supports_search: bool
    supports_listing_lookup: bool
    supports_price_tracking: bool
    supports_refresh: bool
