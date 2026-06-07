from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.p72_grading_analytics import P72GradingAnalyticsDashboardRead
from app.schemas.p72_grading_operations import P72GradingOperationsDashboardRead


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
    decision_engine: P72GradingDecisionDashboardRead | None = None
    operations_engine: P72GradingOperationsDashboardRead | None = None
    analytics_engine: P72GradingAnalyticsDashboardRead | None = None
    status: str = "OK"
    message: str = ""


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


class P72GradeProbabilitiesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade_9_8: float = Field(serialization_alias="9.8")
    grade_9_6: float = Field(serialization_alias="9.6")
    grade_9_4: float = Field(serialization_alias="9.4")
    grade_9_2: float = Field(serialization_alias="9.2")
    grade_other: float = Field(serialization_alias="other")

    def as_probability_map(self) -> dict[str, float]:
        return {
            "9.8": self.grade_9_8,
            "9.6": self.grade_9_6,
            "9.4": self.grade_9_4,
            "9.2": self.grade_9_2,
            "other": self.grade_other,
        }


class P72GradingDecisionCandidateRead(BaseModel):
    """P72-01 read-only grading decision row (not P37 ops registry)."""

    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    raw_fmv: float
    blended_fmv: float
    liquidity_score: float
    market_confidence: float
    sales_velocity: float
    sell_intelligence_score: float
    recommendation: str
    pressing_recommendation: str
    expected_grade: str
    grade_probabilities: dict[str, float]
    expected_graded_fmv: float
    expected_total_cost: float
    expected_profit: float
    expected_roi_pct: float
    grading_score: float
    confidence: float
    primary_reason: str
    factors_json: dict[str, object] = Field(default_factory=dict)


class P72GradingCandidatesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P72GradingDecisionCandidateRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P72GradingDecisionDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_count: int
    average_grading_score: float
    average_expected_roi_pct: float
    press_and_grade_count: int
    grade_count: int
    watch_count: int
    do_not_grade_count: int
    top_grade_candidates: list[P72GradingDecisionCandidateRead] = Field(default_factory=list)
