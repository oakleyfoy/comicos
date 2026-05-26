"""P37-04 schemas for deterministic grading submission batches."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingSubmissionTargetGrader = Literal["PSA", "CGC", "CBCS"]
GradingSubmissionBatchStatus = Literal[
    "DRAFT",
    "READY",
    "SHIPPED",
    "RECEIVED_BY_GRADER",
    "GRADING",
    "RETURN_SHIPPED",
    "COMPLETED",
    "CANCELLED",
]
GradingSubmissionItemStatus = Literal["INCLUDED", "SHIPPED", "RECEIVED", "GRADED", "RETURNED", "CANCELLED"]
GradingSubmissionShipmentDirection = Literal["OUTBOUND", "RETURN"]
GradingSubmissionLifecycleEventType = Literal[
    "CREATED",
    "READY",
    "SHIPPED",
    "RECEIVED_BY_GRADER",
    "GRADING_STARTED",
    "RETURN_SHIPPED",
    "COMPLETED",
    "CANCELLED",
    "UPDATED",
]


class GradingSubmissionCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_candidate_ids: list[int] = Field(..., min_length=1)
    target_grader: GradingSubmissionTargetGrader = Field(...)
    batch_name: str = Field(..., min_length=1, max_length=160)
    submission_date: date | None = None
    estimated_turnaround_days: int | None = Field(default=None, ge=0)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=8000)


class GradingSubmissionPatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_name: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=8000)
    estimated_turnaround_days: int | None = Field(default=None, ge=0)


class GradingSubmissionShipmentCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_direction: GradingSubmissionShipmentDirection = Field(...)
    carrier: str | None = Field(default=None, max_length=80)
    tracking_number: str | None = Field(default=None, max_length=120)
    shipped_date: date | None = None
    delivered_date: date | None = None
    insured_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    shipping_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    notes: str | None = Field(default=None, max_length=8000)


class GradingSubmissionItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_submission_batch_id: int
    grading_candidate_id: int
    inventory_item_id: int
    declared_value: Decimal | None
    estimated_grade: str | None
    final_grade: str | None
    submission_fee: Decimal | None
    status: str
    created_at: datetime
    updated_at: datetime


class GradingSubmissionShipmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_submission_batch_id: int
    shipment_direction: str
    carrier: str | None
    tracking_number: str | None
    shipped_date: date | None
    delivered_date: date | None
    insured_amount: Decimal | None
    shipping_cost: Decimal | None
    notes: str | None
    created_at: datetime


class GradingSubmissionLifecycleEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_submission_batch_id: int
    event_type: str
    prior_status: str | None
    new_status: str | None
    metadata_json: dict[str, object]
    created_by_user_id: int | None
    created_at: datetime


class GradingSubmissionCostSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_submission_batch_id: int
    estimated_grading_fees: Decimal
    estimated_shipping_cost: Decimal
    estimated_insurance_cost: Decimal
    actual_grading_fees: Decimal | None
    actual_shipping_cost: Decimal | None
    actual_insurance_cost: Decimal | None
    checksum: str
    created_at: datetime


class GradingSubmissionBatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    target_grader: str
    batch_name: str
    status: str
    submission_date: date | None
    shipped_date: date | None
    grader_received_date: date | None
    grading_started_date: date | None
    return_shipped_date: date | None
    completed_date: date | None
    estimated_turnaround_days: int | None
    actual_turnaround_days: int | None
    estimated_total_cost: Decimal | None
    actual_total_cost: Decimal | None
    item_count: int
    replay_key: str | None
    checksum: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class GradingSubmissionDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch: GradingSubmissionBatchRead
    items: list[GradingSubmissionItemRead]
    shipments: list[GradingSubmissionShipmentRead]
    lifecycle_events: list[GradingSubmissionLifecycleEventRead]
    cost_snapshots: list[GradingSubmissionCostSnapshotRead]


class GradingSubmissionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSubmissionBatchRead]
    total_items: int
    limit: int
    offset: int


class GradingSubmissionShipmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSubmissionShipmentRead]
    total_items: int
    limit: int
    offset: int


class GradingSubmissionEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingSubmissionLifecycleEventRead]
    total_items: int
    limit: int
    offset: int


class GradingSubmissionDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_batch_count: int
    shipped_batch_count: int
    grading_batch_count: int
    completed_batch_count: int
    average_turnaround_days: Decimal | None


class InventoryGradingSubmissionBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_submission_batch_id: int
    status: str
    target_grader: str
    batch_name: str
    shipment_state: str | None
    item_count: int
