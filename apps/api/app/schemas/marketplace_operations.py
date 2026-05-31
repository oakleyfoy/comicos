from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceRecommendationEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    evidence_type: str
    evidence_source: str
    evidence_payload_json: dict[str, Any]
    evidence_score: float = Field(ge=0.0)
    created_at: datetime


class MarketplaceRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    review_status: str
    reviewed_by: str
    reviewed_at: datetime
    review_notes: str | None = None


class MarketplaceRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_uuid: str
    agent_execution_id: int | None = None
    recommendation_type: str
    title: str
    description: str
    confidence_score: float = Field(ge=0.0)
    priority_score: float = Field(ge=0.0)
    recommendation_status: str
    listing_id: int | None = None
    inventory_copy_id: int | None = None
    marketplace_id: int | None = None
    marketplace_account_id: int | None = None
    created_at: datetime
    latest_review: MarketplaceRecommendationReviewRead | None = None


class MarketplaceRecommendationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: MarketplaceRecommendationRead
    evidence: list[MarketplaceRecommendationEvidenceRead] = Field(default_factory=list)
    reviews: list[MarketplaceRecommendationReviewRead] = Field(default_factory=list)


class MarketplaceRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceRecommendationRead]
    total_items: int
    limit: int
    offset: int
    dashboard: MarketplaceOperationsDashboardRead | None = None


class MarketplaceOperationsDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_recommendations: int
    open_recommendations: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class MarketplaceOperationsRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_execution_id: int | None = None
    recommendations_created: int
    dashboard: MarketplaceOperationsDashboardRead
    recommendations: list[MarketplaceRecommendationRead] = Field(default_factory=list)
