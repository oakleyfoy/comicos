"""P71 Sell Intelligence API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class P71ExitRecommendationSnapshotRead(_Orm):
    id: int
    snapshot_date: date
    generated_at: datetime
    total_items: int
    metadata_json: dict = Field(default_factory=dict)


class P71ExitRecommendationItemRead(_Orm):
    id: int
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    recommendation: str
    exit_score: float
    exit_confidence: float
    primary_reason: str
    secondary_reasons: list[str] = Field(default_factory=list)


class P71ExitRecommendationsListRead(BaseModel):
    snapshot: P71ExitRecommendationSnapshotRead | None = None
    items: list[P71ExitRecommendationItemRead] = Field(default_factory=list)


class P71ListingItemRead(_Orm):
    id: int
    inventory_copy_id: int
    title: str
    suggested_bin: float | None = None
    suggested_auction_start: float | None = None
    expected_sale_low: float | None = None
    expected_sale_high: float | None = None
    expected_profit: float
    expected_roi_pct: float
    expected_days_to_sell: float
    listing_recommendation: str


class P71ListingListRead(BaseModel):
    snapshot_id: int | None = None
    items: list[P71ListingItemRead] = Field(default_factory=list)


class P71LiquidityItemRead(_Orm):
    id: int
    inventory_copy_id: int
    title: str
    liquidity_band: str
    liquidity_score: float
    sales_velocity: float
    observation_count: int
    demand_strength: float
    market_confidence: float
    days_to_sell_estimate: float


class P71LiquidityListRead(BaseModel):
    snapshot_id: int | None = None
    items: list[P71LiquidityItemRead] = Field(default_factory=list)


class P71ExitQueueItemRead(_Orm):
    id: int
    inventory_copy_id: int
    title: str
    priority: int
    expected_profit: float
    expected_roi_pct: float
    confidence: float
    recommended_action: str
    target_price: float | None = None
    expected_days: float


class P71ExitQueueListRead(BaseModel):
    snapshot_id: int | None = None
    items: list[P71ExitQueueItemRead] = Field(default_factory=list)


class P71SellDashboardRead(_Orm):
    id: int
    snapshot_date: date
    generated_at: datetime
    expected_realized_profit: float
    cards_json: dict = Field(default_factory=dict)


class P71PlatformBuildRead(BaseModel):
    steps: list[dict] = Field(default_factory=list)


class P71CertificationRead(BaseModel):
    owner_user_id: int
    certified: bool
    checks: list[dict] = Field(default_factory=list)
    platform: str
