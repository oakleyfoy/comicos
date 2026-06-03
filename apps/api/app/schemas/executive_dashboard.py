from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.recommendation_ranking import RecommendationRankingDiagnosticsRead

SECTION_DAILY_ACTIONS = "DAILY_ACTIONS"
SECTION_TOP_RECOMMENDATIONS = "TOP_RECOMMENDATIONS"
SECTION_PREORDER_THIS_WEEK = "PREORDER_THIS_WEEK"
SECTION_ACQUIRE_TARGETS = "ACQUIRE_TARGETS"
SECTION_GRADE_OPPORTUNITIES = "GRADE_OPPORTUNITIES"
SECTION_SELL_OPPORTUNITIES = "SELL_OPPORTUNITIES"
SECTION_PORTFOLIO_RISK = "PORTFOLIO_RISK"
SECTION_WATCH_ITEMS = "WATCH_ITEMS"
SECTION_SYSTEM_HEALTH = "SYSTEM_HEALTH"

EXECUTIVE_SECTIONS = (
    SECTION_DAILY_ACTIONS,
    SECTION_TOP_RECOMMENDATIONS,
    SECTION_PREORDER_THIS_WEEK,
    SECTION_ACQUIRE_TARGETS,
    SECTION_GRADE_OPPORTUNITIES,
    SECTION_SELL_OPPORTUNITIES,
    SECTION_PORTFOLIO_RISK,
    SECTION_WATCH_ITEMS,
    SECTION_SYSTEM_HEALTH,
)


class ExecutiveDashboardSummaryRead(BaseModel):
    total_daily_actions: int = 0
    critical_daily_actions: int = 0
    top_recommendations_count: int = 0
    preorder_action_count: int = 0
    acquisition_target_count: int = 0
    grading_opportunity_count: int = 0
    sell_opportunity_count: int = 0
    rebalance_warning_count: int = 0
    review_required_count: int = 0
    estimated_capital_recovery: float = 0.0
    budget_remaining: float | None = None


class ExecutiveDashboardItemRead(BaseModel):
    section: str
    item_type: str
    item_id: int
    title: str = ""
    publisher: str = ""
    action_type: str | None = None
    recommendation_type: str | None = None
    priority_score: float | None = None
    confidence_score: float | None = None
    recommendation_rank: int | None = None
    due_date: date | None = None
    estimated_value: float | None = None
    rationale: str = ""
    source_systems: list[str] = Field(default_factory=list)
    health_status: str | None = None
    created_at: str = ""


class ExecutiveDashboardSectionRead(BaseModel):
    section: str
    title: str
    empty_message: str
    items: list[ExecutiveDashboardItemRead] = Field(default_factory=list)
    ranking_diagnostics: RecommendationRankingDiagnosticsRead | None = None


class ExecutiveDashboardRead(BaseModel):
    summary: ExecutiveDashboardSummaryRead
    daily_actions: ExecutiveDashboardSectionRead
    top_recommendations: ExecutiveDashboardSectionRead
    preorder_this_week: ExecutiveDashboardSectionRead
    acquire_targets: ExecutiveDashboardSectionRead
    grade_opportunities: ExecutiveDashboardSectionRead
    sell_opportunities: ExecutiveDashboardSectionRead
    portfolio_risk: ExecutiveDashboardSectionRead
    watch_items: ExecutiveDashboardSectionRead
    system_health: ExecutiveDashboardSectionRead


class ExecutiveDashboardActionsRead(BaseModel):
    priority_actions: list[ExecutiveDashboardItemRead] = Field(default_factory=list)
