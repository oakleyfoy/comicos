from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OcrReplayType = Literal[
    "ocr_result",
    "candidate_extraction",
    "barcode_extraction",
    "fingerprint_generation",
    "reconciliation_warning",
    "quality_analysis",
    "full_pipeline",
]
OcrReplayRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_changes",
    "failed",
    "cancelled",
]
OcrReplayItemStatus = Literal["pending", "running", "unchanged", "changed", "failed", "cancelled"]


class OcrReplayCreatePayload(BaseModel):
    replay_type: OcrReplayType
    cover_image_ids: list[int] = Field(min_length=1)


class OcrReplayItemRead(BaseModel):
    id: int
    replay_run_id: int
    cover_image_id: int
    status: OcrReplayItemStatus
    previous_snapshot_json: dict = Field(default_factory=dict)
    replay_snapshot_json: dict = Field(default_factory=dict)
    diff_summary_json: dict = Field(default_factory=dict)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class OcrReplayRunRead(BaseModel):
    id: int
    replay_type: OcrReplayType
    extraction_version_from: str
    extraction_version_to: str
    status: OcrReplayRunStatus
    total_items: int = 0
    changed_items: int = 0
    unchanged_items: int = 0
    failed_items: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: int | None = None
    items: list[OcrReplayItemRead] = Field(default_factory=list)
