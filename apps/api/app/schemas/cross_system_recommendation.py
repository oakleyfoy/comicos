from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CrossSystemRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    recommendation_type: str
    priority_score: float
    confidence_score: float
    title: str
    estimated_value: float | None = None
    recommendation_rank: int
    source_systems: list[str] = Field(default_factory=list)
    rationale: str
    created_at: datetime


class CrossSystemRecommendationSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_recommendations: int
    top_acquisitions: int
    top_preorders: int
    top_grading_opportunities: int
    top_sell_opportunities: int
    top_rebalance_opportunities: int


class CrossSystemRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CrossSystemRecommendationRead]
    total_items: int
    limit: int
    offset: int
