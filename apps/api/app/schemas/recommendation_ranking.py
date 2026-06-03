from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRankingAuditRow(BaseModel):
    rank: int
    title: str
    priority_score: float
    confidence_score: float
    recommendation_type: str
    raw_priority_score: float | None = None
    normalized_priority_score: float | None = None
    computed_priority_score: float | None = None
    raw_confidence_score: float | None = None
    normalized_confidence_score: float | None = None
    computed_confidence_score: float | None = None
    base_score: float | None = None
    franchise_score: float | None = None
    publisher_score: float | None = None
    creator_score: float | None = None
    milestone_score: float | None = None
    homage_score: float | None = None
    audience_score: float | None = None
    collector_ranking_boost: float | None = None
    final_pre_spread_score: float | None = None


class IntelligenceSignalContribution(BaseModel):
    signal: str
    total_weighted_points: float = 0.0
    average_component_score: float = 0.0
    rows_with_signal: int = 0


class IntelligenceLeaderRow(BaseModel):
    title: str
    score: float
    rank: int


class RecommendationIntelligenceAuditRead(BaseModel):
    listed_count: int = 0
    rank_order_affected_by_intelligence: bool = False
    contribution: list[IntelligenceSignalContribution] = Field(default_factory=list)
    top_milestone: list[IntelligenceLeaderRow] = Field(default_factory=list)
    top_creator: list[IntelligenceLeaderRow] = Field(default_factory=list)
    top_homage: list[IntelligenceLeaderRow] = Field(default_factory=list)


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
    intelligence: RecommendationIntelligenceAuditRead | None = None
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
