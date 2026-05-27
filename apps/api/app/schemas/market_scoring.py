from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketAcquisitionRecommendationLabel = Literal["IGNORE", "WATCH", "BUY", "STRONG_BUY"]
MarketAcquisitionConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]
MarketAcquisitionRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
MarketAcquisitionScoreEvidenceType = Literal[
    "PORTFOLIO_STATE",
    "CONCENTRATION_RISK",
    "DUPLICATE_INTELLIGENCE",
    "LIQUIDITY_ENGINE",
    "NORMALIZATION_LAYER",
]


class MarketAcquisitionScoreRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = None


class MarketAcquisitionScoreSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    total_candidates_scored: int
    avg_score: Decimal | None = None
    avg_liquidity_score: Decimal | None = None
    avg_grading_upside_score: Decimal | None = None
    high_value_count: int
    strong_buy_count: int
    buy_count: int
    watch_count: int
    ignore_count: int
    portfolio_alignment_score: Decimal | None = None
    liquidity_alignment_score: Decimal | None = None
    diversification_alignment_score: Decimal | None = None
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_score_snapshot_id: int
    normalized_candidate_id: int
    canonical_comic_issue_id: int | None = None
    owner_user_id: int | None = None
    acquisition_score: Decimal | None = None
    portfolio_fit_score: Decimal | None = None
    liquidity_score: Decimal | None = None
    grading_upside_score: Decimal | None = None
    concentration_reduction_score: Decimal | None = None
    diversification_score: Decimal | None = None
    risk_penalty_score: Decimal | None = None
    final_rank_score: Decimal | None = None
    score_breakdown_json: dict[str, Any]
    recommendation_label: MarketAcquisitionRecommendationLabel | str
    confidence_level: MarketAcquisitionConfidenceLevel | str
    risk_level: MarketAcquisitionRiskLevel | str
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionScoreEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score_id: int
    evidence_type: MarketAcquisitionScoreEvidenceType | str
    source_id: int | None = None
    source_table: str | None = None
    evidence_value_json: dict[str, Any]
    created_at: datetime


class MarketAcquisitionScoreHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    normalized_candidate_id: int
    acquisition_score: Decimal | None = None
    recommendation_label: MarketAcquisitionRecommendationLabel | str
    confidence_level: MarketAcquisitionConfidenceLevel | str
    risk_level: MarketAcquisitionRiskLevel | str
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionScoreDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: MarketAcquisitionScoreRead
    evidence: list[MarketAcquisitionScoreEvidenceRead] = Field(default_factory=list)


class MarketAcquisitionScoreRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    snapshot: MarketAcquisitionScoreSnapshotRead
    total_scores: int


class MarketAcquisitionScoreListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionScoreRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionScoreSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionScoreSnapshotRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionScoreHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionScoreHistoryRead]
    total_items: int
    limit: int
    offset: int


class InventoryMarketAcquisitionScoreTeaser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_candidate_id: int
    final_rank_score: str | None = None
    recommendation_label: str
    confidence_level: str
    risk_level: str
    liquidity_score: str | None = None
    grading_upside_score: str | None = None
    snapshot_date: date
