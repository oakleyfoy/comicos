"""P90-03 Collector Advisor schemas."""

from __future__ import annotations

from datetime import date, datetime

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


class P90AdvisorTodayActionRead(BaseModel):
    rank: int
    category: str
    title: str
    detail: str = ""
    priority_score: float = 0.0
    action_route: str = ""


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


class P90CollectorAdvisorDashboardRead(BaseModel):
    status: str
    plan: P90CollectorAdvisorSnapshotRead | None = None
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
