"""P78-02 marketplace lifecycle and analytics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LifecycleStatus = Literal[
    "CANDIDATE",
    "DRAFT",
    "READY",
    "LISTED",
    "SOLD",
    "SHIPPED",
    "COMPLETED",
]
SyncState = Literal["ACTIVE", "SOLD", "ENDED", "CANCELLED"]


class P78ListingRead(BaseModel):
    id: int
    listing_draft_id: int
    owner_user_id: int
    inventory_copy_id: int | None
    lifecycle_status: LifecycleStatus
    sync_state: SyncState
    marketplace: str
    external_listing_id: str | None = None
    listing_url: str | None = None
    title: str
    description: str = ""
    condition_label: str
    asking_price: float
    sold_price: float | None = None
    quantity_listed: int
    quantity_reserved: int
    fees: float = 0.0
    shipping_cost: float = 0.0
    listed_at: datetime | None = None
    sold_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    available_copies_hint: int | None = None


class P78ListingListResponse(BaseModel):
    items: list[P78ListingRead]
    total_items: int
    limit: int
    offset: int


class P78ListingUpdate(BaseModel):
    lifecycle_status: LifecycleStatus | None = None
    asking_price: float | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=512)
    description: str | None = None


class P78ListingPublishRead(BaseModel):
    listing: P78ListingRead
    reserved_copy_ids: list[int] = Field(default_factory=list)
    export_payload: dict = Field(default_factory=dict)


class P78ListingSyncRead(BaseModel):
    listings_checked: int
    listings_updated: int
    sales_recorded: int


class P78SaleRecordRead(BaseModel):
    id: int
    listing_id: int
    marketplace: str
    sale_price: float
    fees: float
    shipping_cost: float
    cost_basis: float
    profit: float
    roi_pct: float
    quantity_sold: int
    sold_at: datetime
    p73_outcome_id: int | None = None


class P78SaleListResponse(BaseModel):
    items: list[P78SaleRecordRead]
    total_items: int
    limit: int
    offset: int


class P78SellingAnalyticsRead(BaseModel):
    revenue: float
    profit: float
    roi_pct: float
    listings_created: int
    listings_sold: int
    sell_conversion_rate_pct: float
    average_days_to_sell: float | None
    sell_recommendation_accuracy_pct: float | None = None
    snapshot_id: int | None = None
    status: str = "OK"
    message: str = ""


class P78SellingDashboardRead(BaseModel):
    analytics: P78SellingAnalyticsRead
    active_listings: list[P78ListingRead] = Field(default_factory=list)
    sold_listings: list[P78ListingRead] = Field(default_factory=list)
    draft_listings: list[dict] = Field(default_factory=list)
    recent_sales: list[P78SaleRecordRead] = Field(default_factory=list)
    status: str = "OK"
    message: str = ""


class P78SellingCertificationCheckRead(BaseModel):
    category: str
    component: str
    passed: bool
    detail: str = ""


class P78SellingCertificationRead(BaseModel):
    platform_status: str
    approved_for_production: bool
    checks_passed: int
    failures: int
    platform_readiness_percent: float
    checks: list[P78SellingCertificationCheckRead] = Field(default_factory=list)
    failure_messages: list[str] = Field(default_factory=list)
    production_checklist: list[dict[str, str]] = Field(default_factory=list)
    reviewed_at: datetime
