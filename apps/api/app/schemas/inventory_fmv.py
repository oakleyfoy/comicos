from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_fmv import (
    MarketFmvConfidenceBucket,
    MarketFmvLiquidityBucket,
    MarketFmvSnapshotRead,
    MarketFmvValuationMethod,
    MarketFmvVolatilityBucket,
)
from app.schemas.market_trends import MarketTrendSnapshotSummaryRead

InventoryValuationScope = Literal[
    "raw",
    "graded",
    "preorder_pending",
    "no_market_data",
    "low_confidence",
    "cancelled_excluded",
]


class InventoryFmvAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inventory_copy_id: int
    current_market_fmv: Decimal | None = None
    fmv_snapshot_id: int | None = None
    fmv_method: MarketFmvValuationMethod | None = None
    fmv_confidence_bucket: MarketFmvConfidenceBucket | None = None
    fmv_liquidity_bucket: MarketFmvLiquidityBucket | None = None
    fmv_volatility_bucket: MarketFmvVolatilityBucket | None = None
    fmv_stale_data: bool | None = None
    fmv_currency_code: str | None = None
    valuation_scope: InventoryValuationScope
    valuation_evidence_json: dict[str, Any] = Field(default_factory=dict)
    market_fmv_snapshot: MarketFmvSnapshotRead | None = None
    market_trend_snapshot: MarketTrendSnapshotSummaryRead | None = None


class PortfolioValueCurrencySummaryRead(BaseModel):
    currency_code: str
    total_active_market_value: Decimal
    raw_market_value: Decimal
    graded_market_value: Decimal
    preorder_informational_value: Decimal
    low_confidence_value: Decimal
    stale_value: Decimal
    no_market_data_count: int
    cancelled_excluded_count: int
    duplicate_group_total_value: Decimal
    duplicate_extra_copy_value: Decimal
    duplicate_value_exposure: Decimal
    duplicate_raw_value: Decimal
    duplicate_graded_value: Decimal


class PortfolioValueSummaryResponse(BaseModel):
    scope: Literal["owner", "ops"]
    scope_user_id: int | None = None
    generated_as_of_date: date
    items: list[PortfolioValueCurrencySummaryRead] = Field(default_factory=list)
