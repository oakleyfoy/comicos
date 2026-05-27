from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketAcquisitionOpportunityClassification = Literal[
    "ELITE_OPPORTUNITY",
    "STRONG_OPPORTUNITY",
    "MODERATE_OPPORTUNITY",
    "LOW_OPPORTUNITY",
]
MarketAcquisitionOpportunityEvidenceType = Literal[
    "SIGNAL_LAYER",
    "SCORING_LAYER",
    "NORMALIZATION_LAYER",
    "PORTFOLIO_CONTEXT",
    "CONCENTRATION_RISK",
]


class MarketAcquisitionOpportunityGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_snapshot_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None


class MarketAcquisitionOpportunitySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_signal_snapshot_id: int
    owner_user_id: int | None = None
    opportunity_classification: MarketAcquisitionOpportunityClassification | str
    total_candidates: int
    total_signals: int
    elite_signal_count: int
    high_signal_count: int
    medium_signal_count: int
    low_signal_count: int
    value_dislocation_count: int
    liquidity_opportunity_count: int
    portfolio_gap_fill_count: int
    concentration_reduction_count: int
    grading_upside_count: int
    redundant_asset_count: int
    high_risk_asset_count: int
    estimated_portfolio_gap_coverage: Decimal
    estimated_liquidity_gain: Decimal
    estimated_diversification_gain: Decimal
    estimated_risk_adjustment: Decimal
    avg_signal_strength: Decimal | None = None
    avg_acquisition_score: Decimal | None = None
    avg_confidence_level: Decimal | None = None
    avg_risk_level: Decimal | None = None
    snapshot_checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionOpportunityItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_opportunity_snapshot_id: int
    candidate_id: int
    market_acquisition_signal_id: int
    owner_user_id: int | None = None
    signal_type: str
    signal_strength: str
    acquisition_score: Decimal | None = None
    confidence_level: str
    risk_level: str
    contribution_weight: Decimal
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionOpportunityEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_opportunity_snapshot_id: int
    evidence_type: MarketAcquisitionOpportunityEvidenceType | str
    source_id: int | None = None
    source_table: str | None = None
    evidence_value_json: dict[str, Any]
    created_at: datetime


class MarketAcquisitionOpportunityHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    market_acquisition_opportunity_snapshot_id: int
    snapshot_checksum: str
    total_candidates: int
    elite_signal_count: int
    high_signal_count: int
    estimated_portfolio_gap_coverage: Decimal
    estimated_diversification_gain: Decimal
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionOpportunityDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: MarketAcquisitionOpportunitySnapshotRead
    items: list[MarketAcquisitionOpportunityItemRead] = Field(default_factory=list)


class MarketAcquisitionOpportunityGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    snapshot: MarketAcquisitionOpportunitySnapshotRead
    total_items: int


class MarketAcquisitionOpportunityItemListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionOpportunityItemRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionOpportunitySnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionOpportunitySnapshotRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionOpportunityEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionOpportunityEvidenceRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionOpportunityHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionOpportunityHistoryRead]
    total_items: int
    limit: int
    offset: int


class InventoryMarketAcquisitionOpportunityTeaser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_classification: str
    signal_strength: str
    snapshot_date: date
