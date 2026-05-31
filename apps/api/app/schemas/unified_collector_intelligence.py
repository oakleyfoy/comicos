from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UnifiedCollectorRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    recommendation_type: str
    priority_score: float
    confidence_score: float
    title: str
    rationale: str
    source_systems: list[str] = Field(default_factory=list)
    created_at: datetime


class UnifiedCollectorSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_recommendations: int
    preorder_count: int
    acquire_count: int
    grade_count: int
    sell_count: int
    rebalance_count: int
    watch_count: int
    multi_source_count: int
    average_priority: float
    average_confidence: float


class UnifiedCollectorListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UnifiedCollectorRecommendationRead]
    total_items: int
    limit: int
    offset: int
