from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_sales import MarketSaleSummaryRead

MarketFmvSnapshotScope = Literal["raw", "graded", "graded_by_company", "graded_by_grade"]
MarketFmvValuationMethod = Literal["median_recent_sales", "weighted_recent_sales"]
MarketFmvConfidenceBucket = Literal["very_high", "high", "medium", "low", "very_low"]
MarketFmvLiquidityBucket = Literal["very_high", "high", "medium", "low", "very_low"]
MarketFmvVolatilityBucket = Literal["stable", "moderate", "volatile"]


class MarketFmvCompReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_fmv_snapshot_id: int
    market_sale_record_id: int
    weighting_factor: float
    included_reason: str
    excluded_reason: str | None = None
    created_at: datetime
    market_sale_record: MarketSaleSummaryRead | None = None


class MarketFmvSnapshotSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_issue_id: int | None = None
    metadata_identity_key: str | None = None
    snapshot_scope: MarketFmvSnapshotScope
    grading_company: str | None = None
    normalized_grade: str | None = None
    currency_code: str
    snapshot_date: date
    comp_count: int
    valuation_method: MarketFmvValuationMethod
    estimated_fmv: Decimal
    confidence_bucket: MarketFmvConfidenceBucket
    liquidity_bucket: MarketFmvLiquidityBucket
    volatility_bucket: MarketFmvVolatilityBucket
    stale_data: bool
    created_at: datetime
    updated_at: datetime


class MarketFmvSnapshotRead(MarketFmvSnapshotSummaryRead):
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    comp_references: list[MarketFmvCompReferenceRead] = Field(default_factory=list)


class MarketFmvSnapshotListResponse(BaseModel):
    items: list[MarketFmvSnapshotSummaryRead] = Field(default_factory=list)
    total: int = 0
    by_confidence_bucket: dict[MarketFmvConfidenceBucket, int] = Field(default_factory=dict)
    by_liquidity_bucket: dict[MarketFmvLiquidityBucket, int] = Field(default_factory=dict)
    stale_count: int = 0


class MarketFmvGenerateResponse(BaseModel):
    snapshot_count: int
    snapshots: list[MarketFmvSnapshotSummaryRead] = Field(default_factory=list)

