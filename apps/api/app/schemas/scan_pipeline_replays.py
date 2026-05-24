"""P34-08 deterministic scan pipeline replay bookkeeping (comparison only — no enqueue)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScanPipelineReplayScope = Literal[
    "ingest",
    "qa",
    "routing",
    "ocr_visibility",
    "high_res_review",
]
ScanPipelineReplayRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "completed_with_failures",
    "cancelled",
]
ScanPipelineReplayItemState = Literal["unchanged", "changed", "failed", "cancelled"]
ScanPipelineReplayDiffCategory = Literal[
    "ingest_state_changed",
    "qa_changed",
    "routing_changed",
    "review_state_changed",
    "OCR_visibility_changed",
]


class ScanPipelineReplayCreatePayload(BaseModel):
    scan_session_id: int = Field(ge=1)
    scopes: list[ScanPipelineReplayScope] = Field(
        default_factory=lambda: ["ingest", "qa", "routing", "ocr_visibility", "high_res_review"],
        min_length=1,
        max_length=8,
    )
    notes: str | None = Field(default=None, max_length=8000)


class ScanPipelineReplayItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    replay_run_id: int
    scan_session_item_id: int
    result_state: ScanPipelineReplayItemState
    diff_categories: list[str] = Field(default_factory=list)
    baseline_snapshot_json: dict = Field(default_factory=dict)
    replay_snapshot_json: dict = Field(default_factory=dict)
    diff_summary_json: dict = Field(default_factory=dict)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ScanPipelineReplayRunSummaryRead(BaseModel):
    """Lightweight recap shown on scan session drill-downs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_session_id: int
    status: ScanPipelineReplayRunStatus
    changed_items: int
    unchanged_items: int
    failed_items: int
    cancelled_items: int
    total_items: int
    created_at: datetime
    completed_at: datetime | None = None


class ScanPipelineReplayRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_session_id: int
    owner_user_id: int
    replay_version: str
    scopes_json: list[str] = Field(default_factory=list)
    cancellation_requested: bool
    status: ScanPipelineReplayRunStatus
    total_items: int
    changed_items: int
    unchanged_items: int
    failed_items: int
    cancelled_items: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[ScanPipelineReplayItemRead] = Field(default_factory=list)


class ScanPipelineReplayListRead(BaseModel):
    items: list[ScanPipelineReplayRunRead] = Field(default_factory=list)
