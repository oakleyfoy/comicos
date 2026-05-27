from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketAcquisitionSignalType = Literal[
    "VALUE_DISLOCATION",
    "LIQUIDITY_OPPORTUNITY",
    "PORTFOLIO_GAP_FILL",
    "CONCENTRATION_REDUCTION",
    "GRADING_UPSIDE",
    "REDUNDANT_ASSET",
    "HIGH_RISK_ASSET",
]
MarketAcquisitionSignalStrength = Literal["LOW", "MEDIUM", "HIGH", "ELITE"]
MarketAcquisitionSignalConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]
MarketAcquisitionSignalRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
MarketAcquisitionSignalEvidenceType = Literal[
    "SOURCE_SCORE",
    "SCORING_FACTORS",
    "TRACEABILITY",
]


class MarketAcquisitionSignalGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_snapshot_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None


class MarketAcquisitionSignalSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_score_snapshot_id: int
    owner_user_id: int
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
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_signal_snapshot_id: int
    scored_candidate_id: int
    owner_user_id: int | None = None
    signal_type: MarketAcquisitionSignalType | str
    signal_strength: MarketAcquisitionSignalStrength | str
    signal_score: Decimal | None = None
    confidence_level: MarketAcquisitionSignalConfidenceLevel | str
    risk_level: MarketAcquisitionSignalRiskLevel | str
    signal_reason_json: dict[str, Any]
    supporting_factors_json: dict[str, Any]
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionSignalEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_acquisition_signal_id: int
    evidence_type: MarketAcquisitionSignalEvidenceType | str
    source_id: int | None = None
    source_table: str | None = None
    evidence_value_json: dict[str, Any]
    created_at: datetime


class MarketAcquisitionSignalHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scored_candidate_id: int
    signal_type: MarketAcquisitionSignalType | str
    signal_strength: MarketAcquisitionSignalStrength | str
    signal_score: Decimal | None = None
    confidence_level: MarketAcquisitionSignalConfidenceLevel | str
    risk_level: MarketAcquisitionSignalRiskLevel | str
    checksum: str
    snapshot_date: date
    created_at: datetime


class MarketAcquisitionSignalDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: MarketAcquisitionSignalRead
    evidence: list[MarketAcquisitionSignalEvidenceRead] = Field(default_factory=list)


class MarketAcquisitionSignalGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    snapshot: MarketAcquisitionSignalSnapshotRead
    total_signals: int


class MarketAcquisitionSignalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionSignalRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionSignalSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionSignalSnapshotRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionSignalEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionSignalEvidenceRead]
    total_items: int
    limit: int
    offset: int


class MarketAcquisitionSignalHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionSignalHistoryRead]
    total_items: int
    limit: int
    offset: int


class InventoryMarketAcquisitionSignalTeaser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: str
    signal_strength: str
    signal_score: str | None = None
    confidence_level: str
    risk_level: str
    snapshot_date: date
