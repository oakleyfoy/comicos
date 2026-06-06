"""P73-03 recommendation feedback intelligence read schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation_analytics import P73RecommendationCategoryPerformanceRead


class P73MarketContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fmv_trend_point_count: int
    market_refresh_run_count: int
    market_signal_strength: float


class P73GradingContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_outcome_count: int
    grading_hit_rate_pct: float
    grading_avg_actual_roi_pct: float


class P73RecommendationConfidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buy_confidence: int
    grade_confidence: int
    sell_confidence: int
    watch_confidence: int
    snapshot_id: int = 0
    generated_at: datetime | None = None


class P73CategoryCalibrationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_category: str
    recommendation_count: int
    success_rate_pct: float
    average_roi_pct: float
    median_roi_pct: float


class P73CategoryCalibrationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P73CategoryCalibrationRead] = Field(default_factory=list)
    total_items: int
    limit: int = 100
    offset: int = 0


class P73TypeEffectivenessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_type: str
    expected_roi_pct: float
    actual_roi_pct: float
    win_rate_pct: float
    loss_rate_pct: float
    accuracy_label: str


class P73RecommendationEffectivenessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    win_rate_pct: float
    loss_rate_pct: float
    expected_roi_pct: float
    actual_roi_pct: float
    recommendation_accuracy_pct: float
    by_type: list[P73TypeEffectivenessRead] = Field(default_factory=list)
    snapshot_id: int = 0
    generated_at: datetime | None = None


class P73RecommendationQualityDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_snapshot_id: int
    generated_at: datetime
    overall_accuracy_pct: float
    overall_roi_pct: float
    confidence: P73RecommendationConfidenceRead
    category_calibration: list[P73CategoryCalibrationRead] = Field(default_factory=list)
    effectiveness: P73RecommendationEffectivenessRead
    category_performance: list[P73RecommendationCategoryPerformanceRead] = Field(default_factory=list)
    best_recommendation_types: list[str] = Field(default_factory=list)
    worst_recommendation_types: list[str] = Field(default_factory=list)
    market_context: P73MarketContextRead
    grading_context: P73GradingContextRead


class P73RecommendationCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    passed: bool
    detail: str


class P73RecommendationCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_for_production: bool
    checks: list[P73RecommendationCertificationCheckRead]
    platform_status: str
    reviewed_at: datetime
