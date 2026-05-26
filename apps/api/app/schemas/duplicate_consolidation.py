"""P38-02 duplicate & consolidation schemas (deterministic observational intelligence)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

ClusterTypeLiteral = Literal[
    "exact_issue",
    "variant_family",
    "graded_overlap",
    "raw_graded_overlap",
    "portfolio_overlap",
]

LiquidityProfileLiteral = Literal["HIGH", "MEDIUM", "LOW"]

DuplicationStatusLiteral = Literal["HEALTHY", "WATCH", "REDUNDANT", "OVEREXPOSED"]

GradingStatusLiteral = Literal["RAW", "GRADED", "GRADING_PIPELINE"]

RecommendationPriorityLiteral = Literal["KEEP", "WATCH", "CONSOLIDATE", "SELL_CANDIDATE"]

RecommendationActionLiteral = Literal[
    "KEEP_BEST_COPY",
    "SELL_DUPLICATES",
    "GRADE_STRONGEST_COPY",
    "REDUCE_EXPOSURE",
    "HOLD",
]

ConfidenceLiteral = Literal["LOW", "MEDIUM", "HIGH"]

RecommendationLedgerStatusLiteral = Literal["ACTIVE", "SUPERSEDED", "ARCHIVED"]


class DuplicateClusterGeneratePayload(BaseModel):
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, max_length=128)


class DuplicateClusterRead(BaseModel):
    id: int
    owner_user_id: int
    canonical_comic_issue_id: int | None = None
    cluster_key: str
    cluster_type: str
    generation_batch_checksum: str
    replay_key: str
    total_item_count: int
    graded_item_count: int
    raw_item_count: int
    total_fmv_amount: Decimal | None = None
    total_cost_basis_amount: Decimal | None = None
    liquidity_profile: str
    duplication_status: str
    checksum: str
    snapshot_date: date
    created_at: datetime


class DuplicateClusterItemRead(BaseModel):
    id: int
    duplicate_cluster_id: int
    inventory_item_id: int
    portfolio_id: int | None = None
    grading_status: str
    estimated_strength_score: Decimal | None = None
    liquidity_score: Decimal | None = None
    current_fmv: Decimal | None = None
    acquisition_cost: Decimal | None = None
    recommendation_priority: str
    created_at: datetime


class DuplicateConsolidationRecommendationRead(BaseModel):
    id: int
    owner_user_id: int
    duplicate_cluster_id: int
    generation_batch_checksum: str
    recommendation_action: str
    rationale_summary: str
    expected_capital_reduction: Decimal | None = None
    estimated_liquidity_improvement: Decimal | None = None
    estimated_portfolio_efficiency_gain: Decimal | None = None
    confidence_level: str
    recommendation_status: str
    checksum: str
    snapshot_date: date
    replay_key: str
    created_at: datetime


class DuplicateHistorySnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    cluster_key: str
    cluster_type: str
    total_item_count: int
    total_fmv_amount: Decimal | None = None
    duplication_status: str
    checksum: str
    generation_batch_checksum: str
    snapshot_date: date
    replay_key: str
    created_at: datetime


class DuplicateClusterListResponse(BaseModel):
    generation_batch_checksum: str | None = None
    snapshot_date: date | None = None
    items: list[DuplicateClusterRead] = Field(default_factory=list)


class DuplicateClusterItemListResponse(BaseModel):
    items: list[DuplicateClusterItemRead] = Field(default_factory=list)


class DuplicateConsolidationRecommendationListResponse(BaseModel):
    items: list[DuplicateConsolidationRecommendationRead] = Field(default_factory=list)


class DuplicateHistoryListResponse(BaseModel):
    items: list[DuplicateHistorySnapshotRead] = Field(default_factory=list)


class DuplicateClusterGenerateResponse(BaseModel):
    replayed: bool = False
    generation_batch_checksum: str
    snapshot_date: date
    snapshot_date_replay_source: Literal["explicit", "inferred_prior_batch"] | None = None
    clusters: list[DuplicateClusterRead]
    consolidation_recommendations: list[DuplicateConsolidationRecommendationRead]
    duplicate_history_snapshots_written: int = 0


class DuplicateOpportunityBrief(BaseModel):
    cluster_id: int
    cluster_key: str
    cluster_type: str
    duplication_status: str
    total_cost_basis_amount: Decimal | None = None
    graded_item_count: int
    raw_item_count: int


class DuplicateIntelligenceSummary(BaseModel):
    generation_batch_checksum: str | None = None
    snapshot_date: date | None = None
    cluster_count: int = 0
    overexposed_cluster_count: int = 0
    redundant_capital_amount: Decimal | None = None
    graded_overlap_cluster_count: int = 0
    raw_graded_overlap_cluster_count: int = 0
    graded_duplicate_units: int = 0
    raw_duplicate_units: int = 0
    strongest_opportunities: list[DuplicateOpportunityBrief] = Field(default_factory=list)


class InventoryDuplicateIntelligenceTeaser(BaseModel):
    """Lightweight duplicate posture for inventory detail."""

    generation_batch_checksum: str | None = None
    cluster_types_present: list[str] = Field(default_factory=list)
    worst_duplication_status: str | None = None
    is_strongest_copy_in_clusters: bool = False
    primary_consolidation_action: str | None = None
    consolidation_teaser: str | None = None
