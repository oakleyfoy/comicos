"""P37-07 schemas for deterministic grading risk and confidence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingRiskLevel = Literal["LOW", "MEDIUM", "HIGH", "EXTREME"]
GradingConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]
GradingRiskEvidenceType = Literal[
    "ROI_ENGINE",
    "SPREAD_ENGINE",
    "RECONCILIATION",
    "LIQUIDITY",
    "MARKET_SALE",
    "GRADER_PERFORMANCE",
    "LISTING_INTELLIGENCE",
    "MANUAL_REVIEW",
]
ConfidenceFactorKey = Literal[
    "liquidity_stability",
    "spread_stability",
    "roi_stability",
    "grader_consistency",
    "market_depth",
    "evidence_volume",
    "reconciliation_history",
]


class GradingRiskGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_candidate_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    recommendation_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class GradingRiskEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_risk_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class ConfidenceFactorSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_risk_snapshot_id: int
    factor_key: str
    factor_score: Decimal
    weighting: Decimal
    created_at: datetime


class RiskHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grading_candidate_id: int | None
    inventory_item_id: int | None
    overall_risk_level: str
    overall_confidence_level: str
    risk_adjusted_roi: Decimal | None
    checksum: str
    snapshot_date: date
    created_at: datetime


class GradingRiskSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    grading_candidate_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    recommendation_id: int | None
    overall_risk_level: str
    overall_confidence_level: str
    liquidity_risk_score: Decimal
    spread_volatility_score: Decimal
    roi_volatility_score: Decimal
    grader_variability_score: Decimal
    reconciliation_variance_score: Decimal
    market_stability_score: Decimal
    evidence_strength_score: Decimal
    risk_adjusted_roi: Decimal | None
    confidence_weight: Decimal | None
    warning_flags_json: list[object]
    evidence_count: int
    checksum: str
    replay_key: str | None
    snapshot_date: date
    created_at: datetime


class GradingRiskDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: GradingRiskSnapshotRead
    evidence: list[GradingRiskEvidenceRead]
    confidence_factors: list[ConfidenceFactorSnapshotRead]
    history: list[RiskHistoryRead]


class GradingRiskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRiskSnapshotRead]
    total_items: int
    limit: int
    offset: int


class GradingRiskEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingRiskEvidenceRead]
    total_items: int
    limit: int
    offset: int


class ConfidenceFactorSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConfidenceFactorSnapshotRead]
    total_items: int
    limit: int
    offset: int


class RiskHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RiskHistoryRead]
    total_items: int
    limit: int
    offset: int


class GradingRiskDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low_risk_count: int
    high_risk_count: int
    high_confidence_count: int
    low_confidence_count: int
    average_risk_adjusted_roi: Decimal | None


class InventoryGradingRiskBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_risk_snapshot_id: int
    overall_risk_level: str
    overall_confidence_level: str
    risk_adjusted_roi: Decimal | None
    confidence_weight: Decimal | None
    warning_flags_json: list[object]
