from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanReviewStatus = Literal["NOT_STARTED", "IN_REVIEW", "NEEDS_MORE_SCAN_DATA", "REVIEW_BLOCKED", "REVIEW_COMPLETE", "ARCHIVED"]
ScanReviewDecisionStatus = Literal["ACCEPTED", "REJECTED", "OVERRIDDEN", "NEEDS_REVIEW", "NOT_APPLICABLE"]
ScanReviewIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanReviewSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    visual_evidence_run_id: int | None = Field(default=None, ge=1)
    grading_assistance_run_id: int | None = Field(default=None, ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)


class ScanReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: str
    decision_status: ScanReviewDecisionStatus | str
    decision_value: str
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason_text: str = Field(min_length=1, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ScanReviewNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: str
    note_text: str = Field(min_length=1, max_length=4000)
    source_system: str | None = None
    source_record_id: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ScanReviewEvidenceActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    source_record_id: int = Field(ge=1)
    action_type: str
    action_status: str
    reason_text: str = Field(min_length=1, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ScanReviewDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    decision_type: str
    decision_status: ScanReviewDecisionStatus | str
    decision_value: str
    confidence_score: float | None = None
    reason_text: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReviewNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    note_type: str
    note_text: str
    source_system: str | None = None
    source_record_id: int | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReviewEvidenceActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    source_system: str
    source_record_id: int
    action_type: str
    action_status: str
    reason_text: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReviewArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanReviewIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    issue_type: str
    severity: ScanReviewIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReviewHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    review_session_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReviewSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    visual_evidence_run_id: int | None = None
    grading_assistance_run_id: int | None = None
    reconciliation_run_id: int | None = None
    review_status: ScanReviewStatus | str
    review_checksum: str
    snapshot_checksum: str
    reviewer_user_id: int | None = None
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ScanReviewSessionDetail(ScanReviewSessionRead):
    decisions: list[ScanReviewDecisionRead] = Field(default_factory=list)
    notes: list[ScanReviewNoteRead] = Field(default_factory=list)
    evidence_actions: list[ScanReviewEvidenceActionRead] = Field(default_factory=list)
    artifacts: list[ScanReviewArtifactRead] = Field(default_factory=list)
    issues: list[ScanReviewIssueRead] = Field(default_factory=list)
    history: list[ScanReviewHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    reconciliation_checksum: str | None = None
    defect_checksum: str | None = None
    aggregation_checksum: str | None = None
    grading_assistance_checksum: str | None = None
    visual_evidence_checksum: str | None = None
    source_preview_data_url: str | None = None
    review_snapshot: dict[str, Any] = Field(default_factory=dict)


class ScanReviewSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReviewSessionRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    blocked_review_count: int = 0
    rescan_request_count: int = 0
    completed_review_count: int = 0


class ScanReviewIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReviewIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)

