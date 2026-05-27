from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PortfolioMarketCouplingType = Literal[
    "DIRECT_MATCH",
    "PARTIAL_MATCH",
    "CATEGORY_MATCH",
    "LIQUIDITY_MATCH",
    "DIVERSIFICATION_MATCH",
    "CONCENTRATION_MATCH",
    "CONCENTRATION_CONFLICT",
]
PortfolioMarketCouplingStrength = Literal["LOW", "MEDIUM", "HIGH", "ELITE"]
PortfolioMarketCouplingEvidenceType = Literal[
    "PORTFOLIO_STATE",
    "MARKET_SIGNAL",
    "MARKET_SCORE",
    "NORMALIZED_CANDIDATE",
    "DUPLICATE_INTELLIGENCE",
    "CONCENTRATION_RISK",
]


class PortfolioMarketCouplingGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_snapshot_id: int | None = Field(default=None, ge=1)


class PortfolioMarketCouplingSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    market_acquisition_opportunity_snapshot_id: int

    portfolio_total_value: Decimal | None = None
    portfolio_total_items: int
    portfolio_diversification_score: Decimal | None = None
    portfolio_concentration_score: Decimal | None = None
    portfolio_liquidity_score: Decimal | None = None

    market_opportunity_count: int
    aligned_opportunity_count: int
    misaligned_opportunity_count: int
    high_fit_market_items: int
    low_fit_market_items: int

    portfolio_market_alignment_score: Decimal | None = None
    diversification_gap_alignment_score: Decimal | None = None
    liquidity_gap_alignment_score: Decimal | None = None
    concentration_offset_score: Decimal | None = None

    signal_coverage_ratio: Decimal | None = None
    scoring_coverage_ratio: Decimal | None = None
    normalization_coverage_ratio: Decimal | None = None

    snapshot_checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioMarketCouplingEdgeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    market_candidate_id: int
    market_acquisition_opportunity_item_id: int
    portfolio_item_id: int | None = None
    coupling_type: PortfolioMarketCouplingType | str
    coupling_strength: PortfolioMarketCouplingStrength | str
    coupling_score: int
    explanation_json: dict[str, Any]
    created_at: datetime


class PortfolioMarketCouplingEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    evidence_type: PortfolioMarketCouplingEvidenceType | str
    source_id: int | None = None
    source_table: str | None = None
    evidence_value_json: dict[str, Any]
    created_at: datetime


class PortfolioMarketCouplingHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    snapshot_id: int
    snapshot_checksum: str
    alignment_score: Decimal | None = None
    market_opportunity_count: int
    high_fit_market_items: int
    snapshot_date: date
    created_at: datetime


class PortfolioMarketCouplingDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: PortfolioMarketCouplingSnapshotRead
    edges: list[PortfolioMarketCouplingEdgeRead]
    evidence: list[PortfolioMarketCouplingEvidenceRead] = Field(default_factory=list)


class PortfolioMarketCouplingGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    snapshot: PortfolioMarketCouplingSnapshotRead
    total_edges: int


class PortfolioMarketCouplingSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int
    items: list[PortfolioMarketCouplingSnapshotRead]
    limit: int
    offset: int


class PortfolioMarketCouplingEdgeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int
    items: list[PortfolioMarketCouplingEdgeRead]
    limit: int
    offset: int


class PortfolioMarketCouplingEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int
    items: list[PortfolioMarketCouplingEvidenceRead]
    limit: int
    offset: int


class PortfolioMarketCouplingHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int
    items: list[PortfolioMarketCouplingHistoryRead]
    limit: int
    offset: int


class InventoryPortfolioMarketCouplingTeaserRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coupling_snapshot_id: int
    portfolio_market_alignment_score: Decimal | None = None
    high_fit_market_items: int
    concentration_conflicts: int
    snapshot_date: date
    snapshot_checksum: str
