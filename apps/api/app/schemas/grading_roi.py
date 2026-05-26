"""P37-03 schemas for deterministic grading ROI intelligence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingRoiStatus = Literal["NEGATIVE", "WEAK", "MODERATE", "STRONG", "ELITE", "INSUFFICIENT_DATA"]
GradingRoiConfidence = Literal["HIGH", "MEDIUM", "LOW"]
GradingRoiTargetGrader = Literal["PSA", "CGC", "CBCS"]
GradingRoiEvidenceType = Literal[
    "SPREAD_ENGINE",
    "FMV",
    "MARKET_SALE",
    "SALES_LEDGER",
    "LIQUIDITY",
    "FEE_SCHEDULE",
    "MANUAL_OVERRIDE",
]
GradingRoiScenarioName = Literal["pessimistic", "baseline", "optimistic"]


class GradingRoiGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_candidate_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    target_grader: GradingRoiTargetGrader = Field(...)
    target_grade: str | None = Field(default=None, max_length=32)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class GradingRoiEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_roi_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class GradingRoiScenarioRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_roi_snapshot_id: int
    scenario_name: str
    target_grade: str | None
    estimated_value: Decimal | None
    estimated_roi_pct: Decimal | None
    liquidity_adjusted_roi: Decimal | None
    created_at: datetime


class GradingRoiHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grading_candidate_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    target_grader: str
    target_grade: str | None
    roi_pct: Decimal | None
    liquidity_adjusted_roi: Decimal | None
    snapshot_date: date
    checksum: str
    created_at: datetime


class GradingRoiRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grading_candidate_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    target_grader: str
    target_grade: str | None
    raw_fmv_amount: Decimal | None
    graded_fmv_amount: Decimal | None
    grading_fee_amount: Decimal | None
    shipping_cost_amount: Decimal | None
    insurance_cost_amount: Decimal | None
    estimated_turnaround_days: int | None
    estimated_total_cost: Decimal | None
    estimated_spread_amount: Decimal | None
    estimated_net_profit: Decimal | None
    estimated_roi_pct: Decimal | None
    liquidity_adjusted_roi: Decimal | None
    break_even_grade: str | None
    roi_status: str
    confidence_level: str
    evidence_count: int
    checksum: str
    snapshot_date: date
    replay_key: str | None
    generation_params_json: dict[str, object]
    created_at: datetime


class GradingRoiDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: GradingRoiRead
    evidence: list[GradingRoiEvidenceRead]
    scenarios: list[GradingRoiScenarioRead]
    history: list[GradingRoiHistoryRead]


class GradingRoiListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRoiRead]
    total_items: int
    limit: int
    offset: int


class GradingRoiEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRoiEvidenceRead]
    total_items: int
    limit: int
    offset: int


class GradingRoiHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRoiHistoryRead]
    total_items: int
    limit: int
    offset: int


class GradingRoiDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong_roi_count: int
    elite_roi_count: int
    negative_roi_count: int
    average_estimated_roi: Decimal | None
    liquidity_adjusted_roi_total: Decimal | None


class InventoryGradingRoiBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_roi_snapshot_id: int
    roi_status: str
    target_grader: str
    target_grade: str | None
    estimated_total_cost: Decimal | None
    estimated_net_profit: Decimal | None
    liquidity_adjusted_roi: Decimal | None
    break_even_grade: str | None
    checksum: str
