from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRankingAuditRow(BaseModel):
    rank: int
    title: str
    priority_score: float
    confidence_score: float
    recommendation_type: str


class RecommendationRankingDiagnosticsRead(BaseModel):
    min_score: float | None = None
    max_score: float | None = None
    average_score: float | None = None
    distinct_score_count: int = 0
    top_20_score_spread: float | None = None
    null_priority_count: int = 0
    sort_order_valid: bool = True
    appears_alphabetical_by_title: bool = False


class RecommendationRankingAuditRead(BaseModel):
    total_count: int = 0
    listed_count: int = 0
    min_score: float | None = None
    max_score: float | None = None
    average_score: float | None = None
    distinct_score_count: int = 0
    top_20_score_spread: float | None = None
    null_priority_count: int = 0
    identical_top_score_count: int = 0
    sort_order_valid: bool = True
    appears_alphabetical_by_title: bool = False
    items: list[RecommendationRankingAuditRow] = Field(default_factory=list)
