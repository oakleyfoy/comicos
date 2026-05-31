from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DealerRecommendationEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    evidence_type: str
    evidence_source: str
    evidence_payload_json: dict[str, object]
    evidence_score: float
    created_at: datetime


class DealerRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    review_status: str
    reviewed_by: str
    reviewed_at: datetime
    review_notes: str | None = None


class DealerRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    agent_execution_id: int | None = None
    recommendation_uuid: str
    recommendation_type: str
    asset_type: str
    asset_id: int | None = None
    title: str
    description: str
    confidence_score: float
    priority_score: float
    recommendation_status: str
    created_at: datetime
    latest_review: DealerRecommendationReviewRead | None = None


class DealerRecommendationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: DealerRecommendationRead
    evidence: list[DealerRecommendationEvidenceRead] = Field(default_factory=list)
    reviews: list[DealerRecommendationReviewRead] = Field(default_factory=list)


class DealerOpportunityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    asset_type: str
    asset_id: int
    opportunity_score: float
    risk_score: float
    forecast_score: float
    demand_score: float
    grading_score: float | None = None
    calculated_at: datetime


class DealerCopilotExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class DealerRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerRecommendationRead]
    total_items: int
    limit: int
    offset: int


class DealerOpportunityScoreListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerOpportunityScoreRead]
    total_items: int
    limit: int
    offset: int


class DealerCopilotExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerCopilotExecutionRead]
    total_items: int
    limit: int
    offset: int


class DealerCopilotRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[DealerRecommendationRead] = Field(default_factory=list)
    opportunities: list[DealerOpportunityScoreRead] = Field(default_factory=list)
    executions: list[DealerCopilotExecutionRead] = Field(default_factory=list)


class DealerCopilotSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_recommendations: int
    open_recommendations: int
    by_type: dict[str, int]
    by_status: dict[str, int]


class DealerCopilotDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: DealerCopilotSummaryRead
    top_buys: list[DealerRecommendationRead] = Field(default_factory=list)
    top_sells: list[DealerRecommendationRead] = Field(default_factory=list)
    top_holds: list[DealerRecommendationRead] = Field(default_factory=list)
    top_grades: list[DealerRecommendationRead] = Field(default_factory=list)
    top_watchlist: list[DealerRecommendationRead] = Field(default_factory=list)
    opportunities: list[DealerOpportunityScoreRead] = Field(default_factory=list)
    executions: list[DealerCopilotExecutionRead] = Field(default_factory=list)
