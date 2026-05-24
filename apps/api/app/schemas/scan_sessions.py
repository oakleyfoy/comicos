"""P34 bulk scan-session API shapes (deterministic persistence only — no OCR pipeline wiring)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scanner_profiles import ScannerProfileSnapshotRead
from app.schemas.scan_pipeline_replays import ScanPipelineReplayRunSummaryRead

ScanSessionType = Literal[
    "bulk_ingest",
    "high_res_review",
    "intake_receiving",
    "rescan",
    "manual_upload",
]
ScanSessionStatus = Literal[
    "pending",
    "active",
    "paused",
    "completed",
    "completed_with_errors",
    "cancelled",
]
ScanIngestStatus = Literal[
    "pending",
    "imported",
    "queued_for_ocr",
    "ocr_complete",
    "review_required",
    "failed",
    "skipped",
]


class InventoryScanSessionOriginRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_session_id: int
    session_type: ScanSessionType
    status: ScanSessionStatus
    scan_session_item_id: int
    sequence_index: int
    ingest_status: ScanIngestStatus
    created_at: datetime
    scanner_profile_id: int | None = None
    scanner_profile_label: str | None = Field(
        default=None,
        description="Human label captured when the scan session row was recorded (frozen).",
    )
    scanner_profile_snapshot: ScannerProfileSnapshotRead | None = None


class ScanSessionStatisticsRead(BaseModel):
    total_scans: int
    ocr_completed: int
    ocr_pending: int
    review_required: int
    failures: int
    skipped: int
    average_image_width: float | None = None
    average_image_height: float | None = None
    duplicate_filename_groups: int
    duplicate_filename_excess_rows: int
    duplicate_image_hash_groups: int
    duplicate_image_hash_excess_rows: int


class ScanSessionItemCreatePayload(BaseModel):
    inventory_copy_id: int | None = None
    cover_image_id: int | None = None
    source_filename: str | None = Field(default=None, max_length=510)
    image_width: int | None = Field(default=None, ge=1)
    image_height: int | None = Field(default=None, ge=1)
    image_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class ScanSessionItemsAppendPayload(BaseModel):
    items: list[ScanSessionItemCreatePayload] = Field(min_length=1)


class ScanSessionItemUpdatePayload(BaseModel):
    ingest_status: ScanIngestStatus
    ingest_error: str | None = Field(default=None, max_length=8000)
    image_width: int | None = Field(default=None, ge=1)
    image_height: int | None = Field(default=None, ge=1)
    image_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class ScanSessionCreatePayload(BaseModel):
    session_type: ScanSessionType = "manual_upload"
    scanner_profile_id: int | None = Field(default=None, description="Pinned preset rows write a frozen snapshot.")
    scanner_profile: str | None = Field(default=None, max_length=120)
    source_device: str | None = Field(default=None, max_length=120)
    session_notes: str | None = Field(default=None, max_length=8000)

    model_config = ConfigDict(extra="ignore")


class ScanSessionSummaryRead(BaseModel):
    """Light summary for dashboards and listings."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    session_type: ScanSessionType
    status: ScanSessionStatus
    total_items: int
    processed_items: int
    failed_items: int
    skipped_items: int
    scanner_profile_id: int | None = None
    scanner_profile: str | None = None
    created_at: datetime
    updated_at: datetime


class ScanSessionDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    session_type: ScanSessionType
    status: ScanSessionStatus
    scanner_profile_id: int | None = None
    scanner_profile: str | None = None
    scanner_profile_snapshot: ScannerProfileSnapshotRead | None = None
    source_device: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    total_items: int
    processed_items: int
    failed_items: int
    skipped_items: int
    session_notes: str | None = None
    statistics: ScanSessionStatisticsRead
    items: list["ScanSessionItemRead"] = Field(default_factory=list)
    latest_scan_pipeline_replay: ScanPipelineReplayRunSummaryRead | None = None
    sessions: list[ScanSessionSummaryRead] = Field(default_factory=list)


class ScanSessionDashboardResponse(BaseModel):
    active_sessions: list[ScanSessionSummaryRead]
    recent_sessions: list[ScanSessionSummaryRead]


class ScanSessionListResponse(BaseModel):
    sessions: list[ScanSessionSummaryRead]


class ScanSessionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_session_id: int
    inventory_copy_id: int | None = None
    cover_image_id: int | None = None
    source_filename: str | None = None
    sequence_index: int
    ingest_status: ScanIngestStatus
    ingest_error: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    image_sha256: str | None = None
    created_at: datetime
    updated_at: datetime


class ScanSessionsQueryParams(BaseModel):
    """Query inputs normalized in services (FastAPI parses primitives separately)."""

    status: ScanSessionStatus | None = None
    session_type: ScanSessionType | None = None
    limit: int = Field(default=50, ge=1, le=250)
    offset: int = Field(default=0, ge=0)


class ScanSessionItemsListRead(BaseModel):
    """Deterministic ingest table payload (sequence ASC then item id ASC)."""

    scan_session_id: int
    session_type: ScanSessionType
    session_status: ScanSessionStatus
    owner_user_id: int
    statistics: ScanSessionStatisticsRead
    items: list[ScanSessionItemRead]


class ScanSessionIngestManifestRow(BaseModel):
    """One row aligned with multipart file order."""

    inventory_copy_id: int | None = Field(
        default=None,
        description="Explicit linkage only — never inferred from OCR or filenames.",
    )
    source_filename: str | None = Field(default=None, max_length=510)
    sequence_index: int | None = Field(default=None, ge=0)


class ScanSessionIngestManifest(BaseModel):
    items: list[ScanSessionIngestManifestRow] = Field(default_factory=list)
