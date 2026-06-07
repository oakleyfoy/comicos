from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.grading_intelligence import (
    GradePredictionRead,
    GradingRecommendationRead,
    GradingRoiAnalysisRead,
)
from app.schemas.grading_validation import (
    GradeCalibrationMetricRead,
    GradingReliabilityMetricRead,
)


class GradingPlatformValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class GradingPlatformValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    platform_certified: bool
    checks: list[GradingPlatformValidationCheckRead]
    status: str = "OK"
    message: str = ""


class GradingPlatformHealthComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_code: str
    title: str
    health_status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class GradingPlatformHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    components: list[GradingPlatformHealthComponentRead]
    status: str = "OK"
    message: str = ""


class GradingPlatformConditionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_count: int
    profile_count: int
    average_condition_score: float
    average_quality_score: float


class GradingPlatformPredictionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_count: int
    average_confidence: float
    recent_predictions: list[GradePredictionRead] = Field(default_factory=list)


class GradingPlatformRecommendationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_count: int
    average_priority: float
    recent_recommendations: list[GradingRecommendationRead] = Field(default_factory=list)


class GradingPlatformRoiSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roi_analysis_count: int
    average_roi_percent: float
    recent_roi: list[GradingRoiAnalysisRead] = Field(default_factory=list)


class GradingPlatformCalibrationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_count: int
    calibration_metric_count: int
    average_accuracy_score: float
    recent_calibration: list[GradeCalibrationMetricRead] = Field(default_factory=list)


class GradingPlatformReliabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reliability_metric_count: int
    drift_event_count: int
    average_reliability_score: float
    recent_reliability: list[GradingReliabilityMetricRead] = Field(default_factory=list)


class GradingPlatformSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition_summary: GradingPlatformConditionSummary
    prediction_summary: GradingPlatformPredictionSummary
    recommendation_summary: GradingPlatformRecommendationSummary
    roi_summary: GradingPlatformRoiSummary
    calibration_summary: GradingPlatformCalibrationSummary
    reliability_summary: GradingPlatformReliabilitySummary
    top_grading_candidates: list[GradingRecommendationRead] = Field(default_factory=list)
    status: str = "OK"
    message: str = ""


class GradingPlatformCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_certified: bool
    validation_status: str
    health_status: str
    summary: str
    go_live_recommendation: str
    certification_notes: list[str] = Field(default_factory=list)
    status: str = "OK"
    message: str = ""
