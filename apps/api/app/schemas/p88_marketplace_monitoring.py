"""P88-03 marketplace monitoring API schemas."""

from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class MarketplaceSavedSearchRead(BaseModel):
    id: int
    name: str
    marketplace: str
    query: str
    series: str
    issue_number: str
    publisher: str
    variant: str
    max_price: float | None
    min_discount_to_fmv: float | None
    condition_filter: str
    is_active: bool
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_error: str
    created_at: datetime
    updated_at: datetime


class MarketplaceSavedSearchCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    marketplace: str = "EBAY"
    query: str = ""
    series: str = ""
    issue_number: str = ""
    publisher: str = ""
    variant: str = ""
    max_price: float | None = Field(default=None, ge=0)
    min_discount_to_fmv: float | None = Field(default=None, ge=0, le=100)
    condition_filter: str = ""
    is_active: bool = True


class MarketplaceSavedSearchUpdatePayload(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    marketplace: str | None = None
    query: str | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    variant: str | None = None
    max_price: float | None = Field(default=None, ge=0)
    min_discount_to_fmv: float | None = Field(default=None, ge=0, le=100)
    condition_filter: str | None = None
    is_active: bool | None = None


class MarketplaceSavedSearchListResponse(BaseModel):
    status: str = "OK"
    items: list[MarketplaceSavedSearchRead]
    total_items: int
    limit: int = 100
    offset: int = 0


class MarketplaceMonitoringRunRead(BaseModel):
    id: int
    saved_search_id: int | None
    searches_run: int
    listings_found: int
    new_listings: int
    price_drops: int
    below_fmv_alerts: int
    watchlist_matches: int
    errors: list[str] = Field(default_factory=list)
    created_at: datetime


class MarketplaceSavedSearchRunResponse(BaseModel):
    saved_search: MarketplaceSavedSearchRead
    run: MarketplaceMonitoringRunRead
    dry_run: bool = False


class MarketplaceSavedSearchDeleteResponse(BaseModel):
    deleted: bool
    id: int


class MarketplaceMonitoringRunListResponse(BaseModel):
    status: str = "OK"
    items: list[MarketplaceMonitoringRunRead]
    total_items: int
    limit: int = 50
    offset: int = 0


class MarketplaceAlertRead(BaseModel):
    id: int
    saved_search_id: int | None
    opportunity_id: int | None
    listing_id: int | None
    alert_type: str
    title: str
    message: str
    severity: str
    status: str
    marketplace: str | None = None
    listing_url: str | None = None
    external_item_id: str | None = None
    price: float | None = None
    shipping_cost: float | None = None
    estimated_fmv: float | None = None
    created_at: datetime
    acknowledged_at: datetime | None


class MarketplaceAlertListResponse(BaseModel):
    status: str = "OK"
    items: list[MarketplaceAlertRead]
    total_items: int
    limit: int = 50
    offset: int = 0


class MarketplaceAlertUpdatePayload(BaseModel):
    status: Literal["ACKNOWLEDGED", "DISMISSED"]
