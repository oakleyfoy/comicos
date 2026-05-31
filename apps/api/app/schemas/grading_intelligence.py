from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field


class GradePredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_uuid: str
    analysis_id: int
    inventory_copy_id: int | None
    grading_scale: str
    predicted_grade: str
    grade_floor: str
    grade_ceiling: str
    confidence_score: float
    created_at: datetime


class GradePredictionEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_id: int
    evidence_type: str
    evidence_payload_json: dict[str, object]
    evidence_score: float
    created_at: datetime


class GradingRoiAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int | None
    inventory_copy_id: int | None
    raw_value: float
    expected_graded_value: float
    grading_cost: float
    expected_profit: float
    expected_roi_percent: float
    created_at: datetime


class GradePredictionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction: GradePredictionRead
    evidence: list[GradePredictionEvidenceRead] = Field(default_factory=list)


class GradingRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_uuid: str
    prediction_id: int | None
    inventory_copy_id: int | None
    recommendation_type: str
    title: str
    description: str
    confidence_score: float
    priority_score: float
    recommendation_status: str
    created_at: datetime


class GradingRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    review_status: str
    reviewed_by: int | None
    reviewed_at: datetime
    review_notes: str


class GradingRecommendationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: GradingRecommendationRead
    reviews: list[GradingRecommendationReviewRead] = Field(default_factory=list)
    roi: GradingRoiAnalysisRead | None = None


class GradingAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class GradePredictionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradePredictionRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class GradingRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRecommendationRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class GradingRoiListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRoiAnalysisRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class GradingAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingAgentExecutionRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class GradingIntelligenceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: int | None = None
    inventory_copy_id: int | None = None


class GradingReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_notes: str = ""


class GradingDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_count: int
    recommendation_count: int
    roi_analysis_count: int
    average_confidence: float
    average_priority: float
    average_roi_percent: float
    prediction_summary: list[GradePredictionRead] = Field(default_factory=list)
    recommendation_summary: list[GradingRecommendationRead] = Field(default_factory=list)
    top_grading_candidates: list[GradingRecommendationRead] = Field(default_factory=list)
    roi_summary: list[GradingRoiAnalysisRead] = Field(default_factory=list)
    agent_activity: list[GradingAgentExecutionRead] = Field(default_factory=list)


class GradePredictionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction: GradePredictionDetail


class GradingRecommendationsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[GradingRecommendationRead] = Field(default_factory=list)


class GradingRoiRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyses: list[GradingRoiAnalysisRead] = Field(default_factory=list)


class GradingPrioritiesRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[GradingRecommendationRead] = Field(default_factory=list)


class GradingReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: GradingRecommendationRead
    review: GradingRecommendationReviewRead
