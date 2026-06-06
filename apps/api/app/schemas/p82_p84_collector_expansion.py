"""P82–P84 API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Rec = Literal["STRONG_BUY", "GOOD_BUY", "WATCH", "PASS"]
RiskCat = Literal["LOW_RISK", "MODERATE_RISK", "HIGH_RISK"]
ScenarioType = Literal[
    "SELL_DUPLICATES",
    "GRADE_TOP_CANDIDATES",
    "MARKET_DROP",
    "MARKET_GAIN",
    "LIQUIDATE_SELL_QUEUE",
]
NotifPriority = Literal["CRITICAL", "HIGH", "NORMAL", "LOW"]
NotifStatus = Literal["UNREAD", "READ", "DISMISSED", "SAVED"]


class MarketplaceAcquisitionOpportunityRead(BaseModel):
    id: int
    marketplace: str
    external_listing_id: str
    listing_url: str
    title: str
    publisher: str
    series: str
    issue: str
    variant: str
    asking_price: float
    estimated_fmv: float
    discount_to_fmv: float
    liquidity: float
    velocity: float
    grading_upside: float
    ownership_status: str
    profile_match_score: float
    opportunity_score: float
    recommendation: Rec
    reasons: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class MarketplaceAcquisitionListResponse(BaseModel):
    items: list[MarketplaceAcquisitionOpportunityRead]
    total_items: int
    limit: int
    offset: int


class MarketplaceAcquisitionScanPayload(BaseModel):
    marketplace: str = "EBAY"
    external_listing_id: str = Field(max_length=128)
    listing_url: str = ""
    title: str
    publisher: str = ""
    series: str = ""
    issue: str = ""
    variant: str = ""
    asking_price: float = Field(ge=0)


class MarketplaceAcquisitionDashboardRead(BaseModel):
    strong_buys: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    good_buys: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    watch: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    pass_list: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    largest_spread: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    best_grading_upside: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    best_profile_matches: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    snapshot_id: int | None = None


class ForecastHorizonRead(BaseModel):
    horizon: str
    forecast_value: float
    forecast_change: float
    confidence: float


class CollectionForecastRead(BaseModel):
    current_value: float
    horizons: list[ForecastHorizonRead]
    top_gain_contributors: list[dict] = Field(default_factory=list)
    top_downside_risks: list[dict] = Field(default_factory=list)
    snapshot_id: int | None = None


class CollectionRiskRead(BaseModel):
    risk_score: float
    risk_category: RiskCat
    factors: dict = Field(default_factory=dict)
    snapshot_id: int | None = None


class CollectionScenarioRequest(BaseModel):
    scenario_type: ScenarioType


class CollectionScenarioRead(BaseModel):
    id: int
    scenario_type: str
    projected_value: float
    cash_generated: float
    risk_change: float
    roi_impact: float
    affected_books: list[dict] = Field(default_factory=list)
    explanation: str


class CollectionOptimizationRead(BaseModel):
    sell_candidates: list[dict] = Field(default_factory=list)
    grade_candidates: list[dict] = Field(default_factory=list)
    hold_candidates: list[dict] = Field(default_factory=list)
    buy_targets: list[dict] = Field(default_factory=list)
    reduce_exposure: list[str] = Field(default_factory=list)
    increase_exposure: list[str] = Field(default_factory=list)


class CollectionValuationDashboardRead(BaseModel):
    forecast: CollectionForecastRead
    risk: CollectionRiskRead
    optimization: CollectionOptimizationRead


class CollectorNotificationRead(BaseModel):
    id: int
    notification_type: str
    priority: NotifPriority
    title: str
    message: str
    related_entity_type: str
    related_entity_id: int | None
    action_url: str
    status: str
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime
    read_at: datetime | None = None
    dismissed_at: datetime | None = None


class CollectorNotificationListResponse(BaseModel):
    items: list[CollectorNotificationRead]
    total_items: int
    limit: int
    offset: int
    unread_count: int = 0


class CollectorNotificationUpdate(BaseModel):
    status: NotifStatus | None = None


class CollectorNotificationDashboardRead(BaseModel):
    unread: list[CollectorNotificationRead] = Field(default_factory=list)
    critical: list[CollectorNotificationRead] = Field(default_factory=list)
    recent: list[CollectorNotificationRead] = Field(default_factory=list)


class CollectorBriefingRead(BaseModel):
    id: int
    briefing_type: str
    briefing_date: date
    sections: dict = Field(default_factory=dict)
    top_actions: list[str] = Field(default_factory=list)
    created_at: datetime


class CollectorCommandCenterRead(BaseModel):
    marketplace_deals: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    collection_forecast: CollectionForecastRead | None = None
    risk_alerts: list[CollectorNotificationRead] = Field(default_factory=list)
    daily_briefing: CollectorBriefingRead | None = None
    top_buy_opportunities: list[MarketplaceAcquisitionOpportunityRead] = Field(default_factory=list)
    top_sell_opportunities: list[dict] = Field(default_factory=list)
    upcoming_foc: list[dict] = Field(default_factory=list)
    discovery_alerts: list[dict] = Field(default_factory=list)
    budget_status: dict = Field(default_factory=dict)
    portfolio_movement: dict = Field(default_factory=dict)
    storage_warnings: list[dict] = Field(default_factory=list)
    grading_candidates: list[dict] = Field(default_factory=list)


class CollectorExpansionCertificationCheckRead(BaseModel):
    category: str
    component: str
    passed: bool
    detail: str = ""


class CollectorExpansionCertificationRead(BaseModel):
    title: str
    status: str
    approved_for_production: bool
    checks_passed: int
    warnings: int
    failures: int
    platform_readiness_percent: float
    production_checklist: list[dict[str, str]] = Field(default_factory=list)
    checks: list[CollectorExpansionCertificationCheckRead] = Field(default_factory=list)


class BriefingGenerateRead(BaseModel):
    daily: CollectorBriefingRead | None = None
    weekly: CollectorBriefingRead | None = None
