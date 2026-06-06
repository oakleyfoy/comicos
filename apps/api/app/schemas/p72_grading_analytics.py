"""P72-03 grading analytics and certification schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class P72GradingOutcomeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    queue_entry_id: int
    inventory_copy_id: int
    title: str
    publisher: str
    recommendation: str
    pressing_recommended: str
    was_pressed: bool
    expected_grade: str
    actual_grade: str
    expected_roi_pct: Decimal
    actual_roi_pct: Decimal
    expected_profit: Decimal
    actual_profit: Decimal
    raw_fmv: Decimal
    graded_value_estimate: Decimal
    actual_grading_cost: Decimal
    recommendation_accuracy: str
    queue_status: str
    recorded_at: datetime


class P72GradingPerformanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    books_submitted: int
    books_returned: int
    books_sold: int
    books_held: int
    average_grade: float
    median_grade: float
    hit_rate_9_8_pct: float
    hit_rate_9_6_plus_pct: float
    grade_distribution_pct: dict[str, float]


class P72GradingRoiAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_grading_spend: float
    total_profit: float
    net_roi_pct: float
    profit_by_publisher: dict[str, float]
    profit_by_series: dict[str, float]
    profit_by_character: dict[str, float]
    profit_by_creator: dict[str, float]
    profit_by_era: dict[str, float]


class P72GradingPressingAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pressed_book_count: int
    non_pressed_book_count: int
    pressed_avg_roi_pct: float
    non_pressed_avg_roi_pct: float
    pressed_avg_grade: float
    non_pressed_avg_grade: float
    roi_difference_pct: float
    grade_difference: float
    pressing_success_rate_pct: float
    pressing_worth_it: bool


class P72GradingRecommendationAccuracyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_accuracy_pct: float
    sample_count: int
    comparisons: list[dict[str, object]] = Field(default_factory=list)


class P72GradingPortfolioImpactRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_books_graded: int
    total_slab_value: float
    total_raw_value: float
    total_graded_value: float
    value_added_through_grading: float


class P72GradingWinLossRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    actual_profit: float
    actual_roi_pct: float
    actual_grade: str
    recommendation: str


class P72GradingAnalyticsDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performance: P72GradingPerformanceRead
    roi: P72GradingRoiAnalyticsRead
    recommendation_accuracy: P72GradingRecommendationAccuracyRead
    pressing: P72GradingPressingAnalyticsRead
    portfolio_impact: P72GradingPortfolioImpactRead
    top_grading_wins: list[P72GradingWinLossRead] = Field(default_factory=list)
    worst_grading_decisions: list[P72GradingWinLossRead] = Field(default_factory=list)
    outcome_count: int


class P72GradingOutcomeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P72GradingOutcomeRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P72GradingCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    passed: bool
    detail: str


class P72GradingCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_for_production: bool
    checks: list[P72GradingCertificationCheckRead] = Field(default_factory=list)
    platform_status: str
    reviewed_at: datetime
