"""P73-02 recommendation performance analytics read schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class P73RecommendationFunnelCountsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations_generated: int
    viewed: int
    purchased: int
    skipped: int
    held: int
    graded: int
    sold: int


class P73RecommendationAdoptionMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view_rate_pct: float
    purchase_rate_pct: float
    watchlist_rate_pct: float
    grade_rate_pct: float
    sell_rate_pct: float


class P73RecommendationAccuracyMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success_rate_pct: float
    failure_rate_pct: float
    average_return_pct: float
    median_return_pct: float
    win_rate_pct: float
    loss_rate_pct: float


class P73RecommendationProfitabilityBreakdownRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    expected_profit: Decimal
    actual_profit: Decimal
    expected_roi_pct: float
    actual_roi_pct: float
    sample_count: int


class P73RecommendationProfitabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_profit: Decimal
    actual_profit: Decimal
    expected_roi_pct: float
    actual_roi_pct: float
    by_publisher: list[P73RecommendationProfitabilityBreakdownRowRead] = Field(default_factory=list)
    by_series: list[P73RecommendationProfitabilityBreakdownRowRead] = Field(default_factory=list)
    by_character: list[P73RecommendationProfitabilityBreakdownRowRead] = Field(default_factory=list)
    by_creator: list[P73RecommendationProfitabilityBreakdownRowRead] = Field(default_factory=list)
    by_recommendation_category: list[P73RecommendationProfitabilityBreakdownRowRead] = Field(default_factory=list)


class P73RecommendationCategoryPerformanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_type: str
    recommendation_count: int
    success_rate_pct: float
    average_roi_pct: float


class P73RecommendationAttributionAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    outcomes: int
    purchases: int
    gradings: int
    sales: int
    profit_total: Decimal


class P73RecommendationOutcomeHighlightRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_id: int
    recommendation_id: str
    series: str
    issue: str
    recommendation_type: str
    actual_roi_pct: float | None
    actual_profit: Decimal | None
    attribution_accurate: bool | None


class P73RecommendationAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    snapshot_date: date
    generated_at: datetime
    funnel: P73RecommendationFunnelCountsRead
    adoption: P73RecommendationAdoptionMetricsRead
    accuracy: P73RecommendationAccuracyMetricsRead


class P73RecommendationPerformanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    funnel: P73RecommendationFunnelCountsRead
    adoption: P73RecommendationAdoptionMetricsRead
    accuracy: P73RecommendationAccuracyMetricsRead


class P73RecommendationCategoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P73RecommendationCategoryPerformanceRead] = Field(default_factory=list)
    total_items: int
    limit: int = 100
    offset: int = 0


class P73RecommendationPerformanceDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performance_summary: P73RecommendationPerformanceRead
    adoption_metrics: P73RecommendationAdoptionMetricsRead
    profitability_metrics: P73RecommendationProfitabilityRead
    category_performance: list[P73RecommendationCategoryPerformanceRead] = Field(default_factory=list)
    attribution_analytics: list[P73RecommendationAttributionAnalyticsRead] = Field(default_factory=list)
    top_wins: list[P73RecommendationOutcomeHighlightRead] = Field(default_factory=list)
    worst_outcomes: list[P73RecommendationOutcomeHighlightRead] = Field(default_factory=list)
