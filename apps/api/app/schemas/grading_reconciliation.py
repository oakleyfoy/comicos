"""P37-05 schemas for deterministic grading reconciliation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingReconciliationAccuracyStatus = Literal[
    "ABOVE_EXPECTATION",
    "MET_EXPECTATION",
    "BELOW_EXPECTATION",
    "INSUFFICIENT_DATA",
]
GradingReconciliationStatus = Literal["PENDING", "RECONCILED", "DISPUTED", "ARCHIVED"]
GradingReconciliationConfidence = Literal["HIGH", "MEDIUM", "LOW"]
GradingReconciliationTargetGrader = Literal["PSA", "CGC", "CBCS"]
GradingReconciliationEvidenceType = Literal[
    "SUBMISSION_BATCH",
    "ROI_ENGINE",
    "SPREAD_ENGINE",
    "MARKET_SALE",
    "FMV",
    "MANUAL_ENTRY",
    "SALES_LEDGER",
]


class GradingReconciliationReconcilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_submission_item_id: int = Field(..., ge=1)
    final_grade: str = Field(..., min_length=1, max_length=32)
    realized_graded_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    reconciled_at: datetime | None = None
    confidence_level: GradingReconciliationConfidence | None = None


class GradingReconciliationEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_reconciliation_record_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class GradingReconciliationHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grading_candidate_id: int | None
    inventory_item_id: int | None
    target_grader: str
    expected_grade: str | None
    actual_grade: str | None
    realized_roi: Decimal | None
    roi_delta: Decimal | None
    snapshot_date: date
    checksum: str
    created_at: datetime


class GraderPerformanceSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int | None
    grader: str
    submission_count: int
    above_expectation_count: int
    met_expectation_count: int
    below_expectation_count: int
    average_roi_delta: Decimal | None
    average_turnaround_days: Decimal | None
    checksum: str
    snapshot_date: date
    created_at: datetime


class GradingReconciliationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    grading_submission_item_id: int
    grading_candidate_id: int
    inventory_item_id: int
    target_grader: str
    expected_grade: str | None
    final_grade: str | None
    expected_raw_value: Decimal | None
    expected_graded_value: Decimal | None
    realized_graded_value: Decimal | None
    expected_roi: Decimal | None
    realized_roi: Decimal | None
    roi_delta: Decimal | None
    grading_accuracy_status: str
    reconciliation_status: str
    confidence_level: str
    checksum: str
    reconciled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GradingReconciliationDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: GradingReconciliationRead
    evidence: list[GradingReconciliationEvidenceRead]
    history: list[GradingReconciliationHistoryRead]


class GradingReconciliationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingReconciliationRead]
    total_items: int
    limit: int
    offset: int


class GradingReconciliationEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingReconciliationEvidenceRead]
    total_items: int
    limit: int
    offset: int


class GradingReconciliationHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingReconciliationHistoryRead]
    total_items: int
    limit: int
    offset: int


class GraderPerformanceSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GraderPerformanceSnapshotRead]
    total_items: int
    limit: int
    offset: int


class GradingReconciliationDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reconciled_count: int
    above_expectation_count: int
    below_expectation_count: int
    average_roi_delta: Decimal | None
    grader_performance: list[GraderPerformanceSnapshotRead]


class InventoryGradingReconciliationBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_reconciliation_record_id: int
    target_grader: str
    final_grade: str | None
    roi_delta: Decimal | None
    grading_accuracy_status: str
    reconciliation_status: str
