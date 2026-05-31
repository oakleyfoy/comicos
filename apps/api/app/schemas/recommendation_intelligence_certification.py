from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecommendationIntelligenceValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class RecommendationIntelligenceValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    checks: list[RecommendationIntelligenceValidationCheckRead]


class RecommendationIntelligenceHealthComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_code: str
    title: str
    health_status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class RecommendationIntelligenceHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    components: list[RecommendationIntelligenceHealthComponentRead]


class RecommendationQualityCalibrationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    total_recommendations: int
    tier_distribution: dict[str, int]
    type_distribution: dict[str, int]
    number_one_count: int
    key_issue_in_top_count: int
    user_preference_component_active: bool
    score_variance: float
    findings: list[str]
    details_json: dict[str, object] = Field(default_factory=dict)


class RecommendationIntelligenceSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_recommendations_v2: int
    must_buy_count: int
    strong_buy_count: int
    buy_count: int
    watch_count: int
    pass_count: int
    investment_number_one_count: int
    start_run_count: int
    key_issue_count: int
    ratio_variant_count: int
    user_preference_match_count: int
    average_score: float
    readiness_score: float
    v1_recommendation_count: int
    v2_run_count: int
    explanation_count: int
    v1_vs_v2_moved_up: int
    v1_vs_v2_moved_down: int


class RecommendationIntelligenceCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_certified: bool
    certification_status: str
    go_live_recommendation: str
    readiness_score: float
    certification_date: datetime
    certification_version: str
    validation_status: str
    health_status: str
    calibration_status: str
    certification_notes: list[str]
