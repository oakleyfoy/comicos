from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanAuthenticationStatus = Literal["PENDING", "COMPLETE", "FAILED", "INCONCLUSIVE"]
ScanAuthenticationIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanAuthenticationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)
    visual_evidence_run_id: int | None = Field(default=None, ge=1)
    historical_comparison_run_id: int | None = Field(default=None, ge=1)
    review_session_id: int | None = Field(default=None, ge=1)


class ScanAuthenticationSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    authentication_run_id: int
    signal_rank: int
    signal_type: str
    signal_category: str
    signal_status: str
    confidence_score: float
    source_system: str
    source_record_id: int | None = None
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanAuthenticationFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    authentication_run_id: int
    finding_rank: int
    finding_type: str
    finding_status: str
    confidence_score: float
    review_priority: str
    finding_text: str
    source_signal_ids_json: list[int]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanAuthenticationArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    authentication_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanAuthenticationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    authentication_run_id: int
    issue_type: str
    severity: ScanAuthenticationIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanAuthenticationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    authentication_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanAuthenticationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    reconciliation_run_id: int | None = None
    visual_evidence_run_id: int | None = None
    historical_comparison_run_id: int | None = None
    review_session_id: int | None = None
    source_checksum: str
    authentication_checksum: str
    authentication_status: ScanAuthenticationStatus | str
    engine_version: str
    rubric_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanAuthenticationRunDetail(ScanAuthenticationRunRead):
    signals: list[ScanAuthenticationSignalRead] = Field(default_factory=list)
    findings: list[ScanAuthenticationFindingRead] = Field(default_factory=list)
    artifacts: list[ScanAuthenticationArtifactRead] = Field(default_factory=list)
    issues: list[ScanAuthenticationIssueRead] = Field(default_factory=list)
    history: list[ScanAuthenticationHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    reconciliation_checksum: str | None = None
    visual_evidence_checksum: str | None = None
    historical_comparison_checksum: str | None = None
    review_checksum: str | None = None
    source_preview_data_url: str | None = None
    review_flag_count: int = 0


class ScanAuthenticationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanAuthenticationRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    unresolved_conflict_count: int = 0
    review_required_count: int = 0


class ScanAuthenticationSignalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanAuthenticationSignalRead]
    total_items: int
    limit: int
    offset: int
    signal_status_counts: dict[str, int] = Field(default_factory=dict)


class ScanAuthenticationFindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanAuthenticationFindingRead]
    total_items: int
    limit: int
    offset: int
    finding_status_counts: dict[str, int] = Field(default_factory=dict)
    review_priority_counts: dict[str, int] = Field(default_factory=dict)


class ScanAuthenticationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanAuthenticationIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)
