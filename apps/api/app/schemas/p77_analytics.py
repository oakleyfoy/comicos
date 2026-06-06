"""P77-03 collector profile analytics schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P77ProfileSummaryRead(BaseModel):
    collector_type: str
    risk_profile: str
    time_horizon: str
    preferred_publishers: list[str] = Field(default_factory=list)
    preferred_characters: list[str] = Field(default_factory=list)
    preferred_creators: list[str] = Field(default_factory=list)


class P77ProfileInfluenceRead(BaseModel):
    publisher_match_pct: float = 0.0
    character_match_pct: float = 0.0
    creator_match_pct: float = 0.0
    goal_match_pct: float = 0.0
    risk_influence_pct: float = 0.0


class P77CollectorAnalyticsRead(BaseModel):
    profile_summary: P77ProfileSummaryRead
    profile_influence: P77ProfileInfluenceRead
    snapshot_id: int | None = None


class P77BudgetCategorySpendRead(BaseModel):
    name: str
    spend: float
    purchase_count: int = 0
    roi_pct: float | None = None


class P77BudgetForecastRead(BaseModel):
    projected_month_end_spend: float
    monthly_budget: float
    status: str


class P77BudgetAnalyticsRead(BaseModel):
    monthly_budget: float
    current_spend: float
    remaining_budget: float
    utilization_percent: float
    budget_state: str
    category_breakdown: list[P77BudgetCategorySpendRead] = Field(default_factory=list)
    forecast: P77BudgetForecastRead
    compliance_score: float = 100.0
    snapshot_id: int | None = None


class P77GoalProgressRead(BaseModel):
    goal_id: int
    title: str
    goal_type: str
    progress_value: float
    target_value: float
    completion_percent: float
    velocity_per_week: float | None = None
    estimated_completion_date: str | None = None


class P77GoalAnalyticsRead(BaseModel):
    goals: list[P77GoalProgressRead] = Field(default_factory=list)
    goal_influenced_recommendation_pct: float = 0.0


class P77AdjustmentCategoryRead(BaseModel):
    category: str
    count: int
    share_pct: float


class P77RecommendationImpactRead(BaseModel):
    recommendations_evaluated: int
    recommendations_adjusted: int
    adjustment_rate_pct: float
    categories: list[P77AdjustmentCategoryRead] = Field(default_factory=list)


class P77PersonalizationPerformanceRead(BaseModel):
    global_recommendation_roi_pct: float
    personalized_recommendation_roi_pct: float
    roi_improvement_pct: float
    quantity_adjustment_count: int
    budget_compliance_pct: float


class P77CollectorAssistantPerformanceRead(BaseModel):
    buy_count: int = 0
    pass_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    grade_count: int = 0
    action_alignment_pct: float = 0.0


class P77RecommendationAnalyticsRead(BaseModel):
    impact: P77RecommendationImpactRead
    performance: P77PersonalizationPerformanceRead


class P77AnalyticsDashboardRead(BaseModel):
    profile_summary: P77ProfileSummaryRead
    profile_influence: P77ProfileInfluenceRead
    budget: P77BudgetAnalyticsRead
    goals: P77GoalAnalyticsRead
    recommendation_impact: P77RecommendationImpactRead
    personalization_performance: P77PersonalizationPerformanceRead
    collector_assistant: P77CollectorAssistantPerformanceRead
    generated_at: datetime
    analytics_snapshot_id: int | None = None
