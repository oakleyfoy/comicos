from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_fmv import MarketFmvSnapshotSummaryRead
from app.schemas.market_sales import MarketSaleSummaryRead

MarketTrendSnapshotScope = Literal["raw", "graded", "graded_by_company", "graded_by_grade"]
MarketTrendWindow = Literal["seven_day", "thirty_day", "ninety_day", "one_year"]
MarketTrendDirection = Literal["rising", "stable", "falling", "volatile"]
MarketTrendStrength = Literal["very_high", "high", "medium", "low", "very_low"]
MarketTrendLiquidityDirection = Literal["improving", "stable", "weakening"]
MarketTrendEvidenceType = Literal["comp_reference", "fmv_snapshot", "liquidity_signal", "volatility_signal"]


class MarketTrendEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_trend_snapshot_id: int
    market_sale_record_id: int | None = None
    market_fmv_snapshot_id: int | None = None
    evidence_type: MarketTrendEvidenceType
    evidence_json: dict[str, Any]
    created_at: datetime
    market_sale_record: MarketSaleSummaryRead | None = None
    market_fmv_snapshot: MarketFmvSnapshotSummaryRead | None = None


class MarketTrendSnapshotSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_issue_id: int | None = None
    metadata_identity_key: str | None = None
    snapshot_scope: MarketTrendSnapshotScope
    grading_company: str | None = None
    normalized_grade: str | None = None
    currency_code: str
    trend_window: MarketTrendWindow
    trend_direction: MarketTrendDirection
    trend_strength: MarketTrendStrength
    liquidity_direction: MarketTrendLiquidityDirection
    comp_count: int
    percent_change: Decimal
    volatility_score: float
    stale_data: bool
    evidence_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MarketTrendSnapshotRead(MarketTrendSnapshotSummaryRead):
    evidence_items: list[MarketTrendEvidenceRead] = Field(default_factory=list)


class MarketTrendSnapshotListResponse(BaseModel):
    items: list[MarketTrendSnapshotSummaryRead] = Field(default_factory=list)
    total: int = 0
    by_trend_direction: dict[MarketTrendDirection, int] = Field(default_factory=dict)
    by_trend_strength: dict[MarketTrendStrength, int] = Field(default_factory=dict)
    by_liquidity_direction: dict[MarketTrendLiquidityDirection, int] = Field(default_factory=dict)
    stale_count: int = 0


class MarketTrendGenerateResponse(BaseModel):
    snapshot_count: int
    snapshots: list[MarketTrendSnapshotSummaryRead] = Field(default_factory=list)
