from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.research_agent import ResearchSnapshotRead


class IntelligenceEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    evidence_type: str
    evidence_source: str
    evidence_payload_json: dict[str, Any]
    evidence_score: float = Field(ge=0.0)
    created_at: datetime


class IntelligenceRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    review_status: str
    reviewed_by: str
    reviewed_at: datetime
    review_notes: str | None = None


class IntelligenceRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_uuid: str
    agent_execution_id: int
    recommendation_type: str
    title: str
    description: str
    confidence_score: float = Field(ge=0.0)
    opportunity_score: float = Field(ge=0.0)
    priority_score: float = Field(ge=0.0)
    inventory_copy_id: int | None = None
    inventory_title: str
    status: str
    recommendation_payload_json: dict[str, Any]
    created_at: datetime
    latest_review: IntelligenceRecommendationReviewRead | None = None


class IntelligenceRecommendationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: IntelligenceRecommendationRead
    evidence: list[IntelligenceEvidenceRead] = Field(default_factory=list)
    reviews: list[IntelligenceRecommendationReviewRead] = Field(default_factory=list)


class IntelligenceRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IntelligenceRecommendationRead]
    total_items: int
    limit: int
    offset: int


class IntelligenceRecommendationTypeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]


class IntelligenceRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: ResearchSnapshotRead
    recommendations: list[IntelligenceRecommendationRead] = Field(default_factory=list)
