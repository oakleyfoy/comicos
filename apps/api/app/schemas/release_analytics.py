"""P74-03 release analytics schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class P74ReleaseOutcomeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    release_issue_id: int
    recommended_quantity: int
    ordered_quantity: int
    actual_quantity_purchased: int
    foc_date: date | None
    release_date: date | None
    market_performance_pct: float
    inventory_performance_pct: float
    actual_profit: Decimal
    actual_roi_pct: float
    outcome_status: str
    purchase_action: str
    recorded_at: datetime


class P74ReleaseAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    outcomes_tracked: int
    success_count: int
    failure_count: int
    platform_confidence_pct: float


class P74FocAccuracyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accuracy_rate_pct: float
    upgrade_accuracy_pct: float
    downgrade_accuracy_pct: float
    missed_opportunity_rate_pct: float
    snapshot_id: int = 0


class P74QuantityAccuracyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success_rate_pct: float
    failure_rate_pct: float
    average_roi_pct: float
    median_roi_pct: float
    by_action: dict[str, dict[str, float]] = Field(default_factory=dict)
    snapshot_id: int = 0


class P74ReleaseCategoryPerformanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_key: str
    sample_count: int
    success_rate_pct: float
    average_roi_pct: float


class P74ReleaseCategoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P74ReleaseCategoryPerformanceRead] = Field(default_factory=list)
    total_items: int
    limit: int = 100
    offset: int = 0


class P74ReleasePerformanceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analytics: P74ReleaseAnalyticsRead
    foc_accuracy: P74FocAccuracyRead
    quantity_accuracy: P74QuantityAccuracyRead
    recent_outcomes: list[P74ReleaseOutcomeRead] = Field(default_factory=list)


class P74ReleaseCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    passed: bool
    detail: str


class P74ReleaseCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_for_production: bool
    checks: list[P74ReleaseCertificationCheckRead]
    platform_status: str
    reviewed_at: datetime


class P74ReleaseIntelligenceAnalyticsDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    upcoming_count: int
    past_performance_count: int
    foc_accuracy: P74FocAccuracyRead
    quantity_accuracy: P74QuantityAccuracyRead
    best_categories: list[P74ReleaseCategoryPerformanceRead] = Field(default_factory=list)
    worst_categories: list[P74ReleaseCategoryPerformanceRead] = Field(default_factory=list)
    certification_status: str
    platform_confidence_pct: float
    recent_outcomes: list[P74ReleaseOutcomeRead] = Field(default_factory=list)
