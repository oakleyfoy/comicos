from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanIntelligenceFeedStatus = Literal["COMPLETE", "COMPLETE_WITH_WARNINGS", "REVIEW_REQUIRED", "FAILED"]
ScanIntelligenceFeedSeverity = Literal["INFO", "SUCCESS", "WARNING", "ERROR", "REVIEW_REQUIRED"]


class ScanIntelligenceFeedRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)
    grading_assistance_run_id: int | None = Field(default=None, ge=1)
    visual_evidence_run_id: int | None = Field(default=None, ge=1)
    review_session_id: int | None = Field(default=None, ge=1)
    historical_comparison_run_id: int | None = Field(default=None, ge=1)
    authentication_run_id: int | None = Field(default=None, ge=1)


class ScanIntelligenceFeedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    feed_run_id: int
    event_rank: int
    timeline_rank: int
    event_category: str
    event_type: str
    severity: ScanIntelligenceFeedSeverity | str
    source_system: str
    event_occurred_at: datetime
    source_record_id: int | None = None
    source_checksum: str | None = None
    lineage_checksum: str | None = None
    event_key: str
    event_payload_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanIntelligenceFeedArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    feed_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    media_type: str | None = None
    text_preview: str | None = None
    body_base64: str | None = None
    created_at: datetime


class ScanIntelligenceFeedIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    feed_run_id: int
    issue_type: str
    severity: ScanIntelligenceFeedSeverity | str
    source_system: str
    source_record_id: int | None = None
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanIntelligenceFeedHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    feed_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanIntelligenceFeedRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    upload_session_id: int | None = None
    ingestion_batch_id: int | None = None
    normalization_run_id: int | None = None
    boundary_run_id: int | None = None
    ocr_run_id: int | None = None
    reconciliation_run_id: int | None = None
    defect_run_id: int | None = None
    spine_tick_run_id: int | None = None
    corner_edge_run_id: int | None = None
    surface_defect_run_id: int | None = None
    structural_damage_run_id: int | None = None
    defect_aggregation_run_id: int | None = None
    grading_assistance_run_id: int | None = None
    visual_evidence_run_id: int | None = None
    review_session_id: int | None = None
    historical_comparison_run_id: int | None = None
    authentication_run_id: int | None = None
    source_checksum: str
    feed_checksum: str
    feed_status: ScanIntelligenceFeedStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    total_events: int
    total_issues: int
    review_required_count: int
    error_count: int
    created_at: datetime
    completed_at: datetime | None = None


class ScanIntelligenceFeedRunDetail(ScanIntelligenceFeedRunRead):
    events: list[ScanIntelligenceFeedEventRead] = Field(default_factory=list)
    artifacts: list[ScanIntelligenceFeedArtifactRead] = Field(default_factory=list)
    issues: list[ScanIntelligenceFeedIssueRead] = Field(default_factory=list)
    history: list[ScanIntelligenceFeedHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    reconciliation_checksum: str | None = None
    defect_checksum: str | None = None
    spine_tick_checksum: str | None = None
    corner_edge_checksum: str | None = None
    surface_defect_checksum: str | None = None
    structural_damage_checksum: str | None = None
    defect_aggregation_checksum: str | None = None
    grading_assistance_checksum: str | None = None
    visual_evidence_checksum: str | None = None
    review_checksum: str | None = None
    historical_comparison_checksum: str | None = None
    authentication_checksum: str | None = None


class ScanIntelligenceFeedRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanIntelligenceFeedRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    total_event_count: int = 0
    total_review_required_count: int = 0
    total_error_count: int = 0


class ScanIntelligenceFeedEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanIntelligenceFeedEventRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    source_system_counts: dict[str, int] = Field(default_factory=dict)


class ScanIntelligenceFeedIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanIntelligenceFeedIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
    issue_type_counts: dict[str, int] = Field(default_factory=dict)
    source_system_counts: dict[str, int] = Field(default_factory=dict)
