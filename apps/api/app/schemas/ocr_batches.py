from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OcrBatchStatus = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_errors",
    "failed",
    "cancelled",
]
OcrBatchItemStatus = Literal[
    "pending",
    "queued",
    "running",
    "completed",
    "failed",
    "skipped",
    "cancelled",
]


class OcrBatchCreatePayload(BaseModel):
    cover_image_ids: list[int] = Field(min_length=1)
    batch_options_json: dict = Field(default_factory=dict)


class OcrBatchItemRead(BaseModel):
    id: int
    batch_id: int
    cover_image_id: int
    status: OcrBatchItemStatus
    job_id: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class OcrBatchRead(BaseModel):
    id: int
    batch_key: str
    status: OcrBatchStatus
    total_items: int = 0
    pending_count: int = 0
    running_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    extraction_version: str
    batch_options_json: dict = Field(default_factory=dict)
    items: list[OcrBatchItemRead] = Field(default_factory=list)
