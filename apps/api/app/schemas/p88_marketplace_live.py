"""P88-02 live marketplace listing API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketplaceListingRead(BaseModel):
    id: int
    marketplace: str
    item_id: str
    title: str
    listing_url: str
    image_url: str
    price: float
    shipping_cost: float
    condition: str
    seller_name: str
    listing_type: str
    end_time: datetime | None
    is_active: bool
    health_status: str
    health_badges: list[str] = Field(default_factory=list)
    marketplace_name: str = ""
    availability_status: str = "UNKNOWN"
    listing_confidence: str = "MEDIUM"
    currency: str = "USD"
    price_last_changed_at: datetime | None = None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MarketplaceSearchMarketplacePayload(BaseModel):
    opportunity_ids: list[int] = Field(default_factory=list)


class MarketplaceSearchMarketplaceResponse(BaseModel):
    listings_found: int
    new_listings: int
    updated_listings: int
    failed_searches: int
    searches_run: int = 0
    errors: list[str] = Field(default_factory=list)


class MarketplaceSearchDashboardRead(BaseModel):
    total_search_runs: int
    recent_searches_run: int
    success_rate_percent: float
    listings_found_total: int
    new_listings_total: int
    updated_listings_total: int
    failed_searches_total: int
    active_listings: int
    ended_listings: int
    recent_errors: list[str] = Field(default_factory=list)


class MarketplaceListingListResponse(BaseModel):
    status: str = "OK"
    items: list[MarketplaceListingRead]
    total_items: int
    limit: int = 200
    offset: int = 0
