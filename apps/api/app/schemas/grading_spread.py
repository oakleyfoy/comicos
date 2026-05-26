"""P37-02 schemas for deterministic grading spread intelligence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingSpreadStatus = Literal["NEGATIVE", "WEAK", "MODERATE", "STRONG", "ELITE", "INSUFFICIENT_DATA"]
GradingSpreadLiquidityModifier = Literal["HIGH", "MEDIUM", "LOW"]
GradingSpreadConfidence = Literal["HIGH", "MEDIUM", "LOW"]
GradingSpreadTargetGrader = Literal["PSA", "CGC", "CBCS"]
GradingSpreadEvidenceType = Literal[
    "RAW_FMV",
    "GRADED_FMV",
    "MARKET_SALE",
    "LIQUIDITY",
    "SALES_LEDGER",
    "LISTING_INTELLIGENCE",
]


class GradingSpreadGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    target_grader: GradingSpreadTargetGrader = Field(...)
    target_grade: str | None = Field(default=None, max_length=32)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class GradingSpreadEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_spread_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class GradingSpreadBandRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    target_grader: str
    target_grade: str | None
    lower_bound_pct: Decimal
    upper_bound_pct: Decimal
    status_label: str
    created_at: datetime


class GradingSpreadHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    target_grader: str
    target_grade: str | None
    spread_amount: Decimal | None
    spread_pct: Decimal | None
    snapshot_date: date
    checksum: str
    created_at: datetime


class GradingSpreadRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    target_grader: str
    target_grade: str | None
    raw_fmv_amount: Decimal | None
    graded_fmv_amount: Decimal | None
    grading_cost_amount: Decimal | None
    estimated_spread_amount: Decimal | None
    estimated_spread_pct: Decimal | None
    estimated_net_upside: Decimal | None
    liquidity_adjusted_upside: Decimal | None
    spread_status: str
    liquidity_modifier: str
    confidence_level: str
    evidence_count: int
    checksum: str
    snapshot_date: date
    replay_key: str | None
    generation_params_json: dict[str, object]
    created_at: datetime


class GradingSpreadDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: GradingSpreadRead
    evidence: list[GradingSpreadEvidenceRead]
    history: list[GradingSpreadHistoryRead]


class GradingSpreadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSpreadRead]
    total_items: int
    limit: int
    offset: int


class GradingSpreadEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSpreadEvidenceRead]
    total_items: int
    limit: int
    offset: int


class GradingSpreadHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSpreadHistoryRead]
    total_items: int
    limit: int
    offset: int


class GradingSpreadDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong_spread_count: int
    elite_spread_count: int
    negative_spread_count: int
    average_estimated_upside: Decimal | None
    liquidity_adjusted_upside_total: Decimal | None


class InventoryGradingSpreadBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_spread_snapshot_id: int
    spread_status: str
    target_grader: str
    target_grade: str | None
    estimated_net_upside: Decimal | None
    liquidity_adjusted_upside: Decimal | None
    checksum: str
