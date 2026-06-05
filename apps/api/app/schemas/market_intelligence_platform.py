"""P63 Market Intelligence API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PortfolioPerformanceItemRead(BaseModel):
    id: int
    owner_id: int
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    quantity: int
    cost_basis: float
    current_value: float
    unrealized_gain: float
    unrealized_gain_pct: float
    demand_score: float
    velocity_score: float
    recommendation_score: float
    performance_tier: str
    notes_json: dict = Field(default_factory=dict)


class PortfolioPerformanceSnapshotRead(BaseModel):
    snapshot_id: int
    snapshot_date: date
    generated_at: datetime
    total_items: int
    total_cost_basis: float
    total_current_value: float
    total_unrealized_gain: float
    total_unrealized_gain_pct: float
    top_gainers_count: int
    top_losers_count: int
    items: list[PortfolioPerformanceItemRead] = Field(default_factory=list)


class PortfolioBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class SellSignalItemRead(BaseModel):
    id: int
    owner_id: int
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    sell_score: float
    hold_score: float
    recommended_action: str
    sell_reason: str
    confidence: str
    status: str
    unrealized_gain_pct: float


class SellSignalListRead(BaseModel):
    snapshot_id: int | None = None
    total_items: int = 0
    strong_sell_count: int = 0
    consider_sell_count: int = 0
    hold_count: int = 0
    items: list[SellSignalItemRead] = Field(default_factory=list)


class SellSignalStatusUpdate(BaseModel):
    status: str


class SellBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class AcquisitionItemRead(BaseModel):
    id: int
    owner_id: int
    title: str
    publisher: str
    issue_number: str
    opportunity_score: float
    demand_score: float
    velocity_score: float
    spec_score: float
    recommendation_score: float
    estimated_market_price: float | None = None
    target_buy_price: float | None = None
    reason: str
    action: str
    status: str


class AcquisitionListRead(BaseModel):
    snapshot_id: int | None = None
    total_items: int = 0
    high_priority_count: int = 0
    watch_count: int = 0
    items: list[AcquisitionItemRead] = Field(default_factory=list)


class AcquisitionStatusUpdate(BaseModel):
    status: str


class AcquisitionBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class MarketSignalItemRead(BaseModel):
    id: int
    title: str
    publisher: str
    issue_number: str
    market_score: float
    signal_type: str
    signal_reason: str
    confidence: str
    demand_score: float
    velocity_score: float
    opportunity_score: float
    risk_score: float


class MarketSignalListRead(BaseModel):
    snapshot_id: int | None = None
    scope: str = "OWNER"
    total_items: int = 0
    items: list[MarketSignalItemRead] = Field(default_factory=list)


class MarketSignalBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class MarketComponentCertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: str


class MarketPlatformCertificationRead(BaseModel):
    platform_ready: bool
    portfolio: dict = Field(default_factory=dict)
    sell_signals: dict = Field(default_factory=dict)
    acquisition: dict = Field(default_factory=dict)
    market_signals: dict = Field(default_factory=dict)
    checked_at: str


class MarketPlatformBuildRead(BaseModel):
    steps: dict[str, str] = Field(default_factory=dict)
    certification: MarketPlatformCertificationRead
