"""P90-03 Collector Advisor schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class P90AdvisorActionRead(BaseModel):
    category: str
    comic: str
    reason: str
    confidence: str = "MEDIUM"
    priority_score: float = 0.0
    potential_upside: float | None = None
    profit_potential: float | None = None
    value_increase: float | None = None
    action_route: str = ""
    source_system: str = ""
    display_label: str = ""
    primary_reason: str = ""
    supporting_signals: list[str] = Field(default_factory=list)
    hidden_signal_count: int = 0
    action_url: str = ""
    action_url_type: str = ""
    has_verified_listing: bool = False
    verified_listing_count: int = 0
    marketplace_name: str | None = None
    recommendation_type: str = ""
    recommendation_type_label: str = ""
    is_verified_deal: bool = False
    is_recommendation_only: bool = True
    price_source: str = ""
    price_source_label: str = ""
    target_buy_price: float | None = None
    estimated_value: float | None = None
    current_price: float | None = None
    estimated_savings: float | None = None
    potential_upside_percent: float | None = None
    why_this_book: str = ""
    why_now: str = ""
    why_for_me: str = ""
    recommended_action: str = ""


class P90AdvisorTodayActionRead(BaseModel):
    rank: int
    category: str
    title: str
    detail: str = ""
    priority_score: float = 0.0
    action_route: str = ""
    potential_upside: float | None = None
    profit_potential: float | None = None
    value_increase: float | None = None
    action_url: str = ""
    action_url_type: str = ""
    has_verified_listing: bool = False
    marketplace_name: str | None = None
    recommendation_type: str = ""
    recommendation_type_label: str = ""
    is_verified_deal: bool = False
    action_pill: str = ""


class P90AdvisorActivityRead(BaseModel):
    activity_type: str
    title: str
    detail: str = ""
    occurred_at: str | None = None


class P90PortfolioImpactRead(BaseModel):
    potential_profit: float = 0.0
    potential_savings: float = 0.0
    potential_value_gain: float = 0.0
    portfolio_impact_total: float = 0.0
    portfolio_score: float = 0.0


class P90CollectorAdvisorSnapshotRead(BaseModel):
    id: int
    snapshot_date: date
    buy_actions: list[P90AdvisorActionRead] = Field(default_factory=list)
    sell_actions: list[P90AdvisorActionRead] = Field(default_factory=list)
    grade_actions: list[P90AdvisorActionRead] = Field(default_factory=list)
    watch_actions: list[P90AdvisorActionRead] = Field(default_factory=list)
    todays_actions: list[P90AdvisorTodayActionRead] = Field(default_factory=list)
    recent_activity: list[P90AdvisorActivityRead] = Field(default_factory=list)
    market_alerts: list[P90AdvisorActivityRead] = Field(default_factory=list)
    total_actions: int = 0
    portfolio_impact: P90PortfolioImpactRead
    created_at: datetime


class P90AdvisorSignalDiagnosticsRead(BaseModel):
    inventory_count: int = 0
    marketplace_opportunity_count: int = 0
    marketplace_alert_count: int = 0
    sell_candidate_count: int = 0
    listing_draft_count: int = 0
    managed_listing_count: int = 0
    future_pull_count: int = 0
    discovery_alert_count: int = 0
    collection_gap_count: int = 0
    automation_alert_count: int = 0
    fmv_snapshot_count: int = 0
    grade_before_sell_count: int = 0
    grading_candidate_count: int = 0
    gather_failed_subsystems: list[str] = Field(default_factory=list)
    gather_errors: list[dict[str, Any]] = Field(default_factory=list)


class P90CollectorAdvisorDashboardRead(BaseModel):
    status: str
    plan: P90CollectorAdvisorSnapshotRead | None = None
    message: str = ""
    signal_diagnostics: P90AdvisorSignalDiagnosticsRead | None = None
    generated_at: datetime


class P90CollectorAdvisorHistoryRead(BaseModel):
    items: list[P90CollectorAdvisorSnapshotRead] = Field(default_factory=list)
    total: int = 0


class P90CollectorAdvisorBriefingSummary(BaseModel):
    top_buy: str | None = None
    top_sell: str | None = None
    top_grade: str | None = None
    top_watch: str | None = None
    portfolio_impact: float = 0.0
    total_actions: int = 0
