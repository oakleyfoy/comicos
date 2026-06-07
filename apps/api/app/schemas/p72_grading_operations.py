"""P72-02 grading operations API schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

P72QueueStatus = Literal[
    "CANDIDATE",
    "READY_TO_SUBMIT",
    "SUBMITTED",
    "AT_CGC",
    "GRADING_COMPLETE",
    "RETURNED",
    "LISTED",
    "SOLD",
]


class P72GradingBatchCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_name: str = Field(..., min_length=1, max_length=160)
    target_grader: str = Field(default="CGC", max_length=16)
    submission_date: date | None = None
    estimated_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    notes: str | None = Field(default=None, max_length=8000)
    queue_entry_ids: list[int] = Field(default_factory=list)


class P72GradingBatchAssignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_entry_ids: list[int] = Field(..., min_length=1)
    move_from_batch_id: int | None = None


class P72GradingBatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    batch_name: str
    target_grader: str
    submission_date: date | None
    book_count: int
    estimated_cost: Decimal | None
    actual_cost: Decimal | None
    grader_received_date: date | None
    estimated_completion_date: date | None
    actual_completion_date: date | None
    turnaround_days: int | None
    batch_status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class P72GradingBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P72GradingBatchRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P72GradingQueueEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    inventory_copy_id: int
    p72_grading_batch_id: int | None
    title: str
    publisher: str
    issue_number: str
    status: str
    target_grader: str
    submission_date: date | None
    received_date: date | None
    estimated_completion_date: date | None
    actual_completion_date: date | None
    turnaround_days: int | None
    estimated_grading_cost: Decimal | None
    actual_grade: str | None
    certification_number: str | None
    slab_notes: str | None
    final_grading_cost: Decimal | None
    created_at: datetime
    updated_at: datetime


class P72GradingQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P72GradingQueueEntryRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0
    status: str = "OK"
    message: str = ""


class P72GradingQueueEnqueuePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_ids: list[int] = Field(..., min_length=1)
    target_grader: str = Field(default="CGC", max_length=16)
    estimated_grading_cost: Decimal | None = None


class P72GradingQueueStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: P72QueueStatus | str
    submission_date: date | None = None
    received_date: date | None = None
    estimated_completion_date: date | None = None
    actual_completion_date: date | None = None
    actual_grade: str | None = Field(default=None, max_length=32)
    certification_number: str | None = Field(default=None, max_length=64)
    slab_notes: str | None = Field(default=None, max_length=8000)
    final_grading_cost: Decimal | None = Field(default=None, ge=Decimal("0"))


class P72GradingAuditLogRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    queue_entry_id: int
    event_type: str
    prior_status: str | None
    new_status: str | None
    metadata_json: dict[str, object]
    created_by_user_id: int | None
    created_at: datetime


class P72GradingOperationsMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_submissions: int
    books_in_process: int
    books_completed: int
    average_turnaround_days: float
    average_grading_cost: float
    total_grading_spend: float
    waiting_count: int
    submitted_count: int
    at_cgc_count: int
    returned_count: int
    listed_count: int
    sold_count: int


class P72GradingQueueEnqueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P72GradingQueueEntryRead] = Field(default_factory=list)
    count: int


class P72GradingOperationsDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: P72GradingOperationsMetricsRead
    batch_summary: list[P72GradingBatchRead] = Field(default_factory=list)
    recent_queue: list[P72GradingQueueEntryRead] = Field(default_factory=list)
