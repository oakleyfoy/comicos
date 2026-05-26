"""P38-03 portfolio liquidity allocation API shapes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PortfolioLiquidityGeneratePayload(BaseModel):
    portfolio_id: int | None = None
    replay_key: str | None = None
    snapshot_date: date | None = None


class PortfolioLiquidityBucketRead(BaseModel):
    id: int
    portfolio_liquidity_snapshot_id: int
    liquidity_bucket: Literal["HIGH", "MEDIUM", "LOW", "ILLIQUID"]
    item_count: int
    total_fmv: Decimal | None
    weighted_liquidity_value: Decimal | None
    percentage_of_portfolio: Decimal | None
    created_at: datetime


class PortfolioLiquiditySnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    portfolio_id: int | None
    generation_scope_key: str
    replay_key: str
    total_portfolio_fmv: Decimal | None
    liquid_portfolio_value: Decimal | None
    illiquid_portfolio_value: Decimal | None
    liquidity_weighted_value: Decimal | None
    liquidity_efficiency_score: Decimal | None
    liquidity_drag_score: Decimal | None
    concentration_risk_score: Decimal | None
    dead_capital_estimate: Decimal | None
    liquidity_balance_status: Literal["HEALTHY", "WATCH", "IMBALANCED", "CRITICAL", "INSUFFICIENT_DATA"]
    high_liquidity_count: int
    medium_liquidity_count: int
    low_liquidity_count: int
    illiquid_count: int
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioLiquidityGenerateResponse(BaseModel):
    replayed: bool
    snapshot: PortfolioLiquiditySnapshotRead
    buckets: list[PortfolioLiquidityBucketRead]
    history_appended: bool


class PortfolioLiquiditySnapshotListResponse(BaseModel):
    items: list[PortfolioLiquiditySnapshotRead]
    total: int


class PortfolioLiquiditySnapshotDetailResponse(BaseModel):
    snapshot: PortfolioLiquiditySnapshotRead
    buckets: list[PortfolioLiquidityBucketRead]


class PortfolioLiquidityEvidenceRead(BaseModel):
    id: int
    portfolio_liquidity_snapshot_id: int
    evidence_type: Literal[
        "LIQUIDITY_ENGINE",
        "FMV",
        "SALES_LEDGER",
        "LISTING_INTELLIGENCE",
        "CONVENTION_ACTIVITY",
        "PORTFOLIO_REGISTRY",
    ]
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class PortfolioLiquidityEvidenceListResponse(BaseModel):
    items: list[PortfolioLiquidityEvidenceRead]
    total: int


class PortfolioLiquidityHistoryRead(BaseModel):
    id: int
    owner_user_id: int
    portfolio_id: int | None
    generation_scope_key: str
    replay_key: str
    liquidity_efficiency_score: Decimal | None
    liquidity_drag_score: Decimal | None
    concentration_risk_score: Decimal | None
    dead_capital_estimate: Decimal | None
    liquidity_balance_status: Literal["HEALTHY", "WATCH", "IMBALANCED", "CRITICAL", "INSUFFICIENT_DATA"]
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioLiquidityHistoryListResponse(BaseModel):
    items: list[PortfolioLiquidityHistoryRead]
    total: int


class InventoryPortfolioLiquidityTeaser(BaseModel):
    portfolio_liquidity_bucket: Literal["HIGH", "MEDIUM", "LOW", "ILLIQUID"]
    liquidity_engine_status: str | None = None
    portfolio_liquidity_snapshot_id: int | None = None
    liquidity_efficiency_score: str | None = None
    dead_capital_estimate: str | None = None
    liquidity_balance_status: str | None = None
    dead_capital_teaser: str | None = None
