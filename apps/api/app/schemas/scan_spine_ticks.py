from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanSpineTickStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanSpineTickIssueSeverity = Literal["INFO", "WARNING", "ERROR"]
ScanSpineTickSeverityHint = Literal["MINOR", "MODERATE", "MAJOR"]


class ScanSpineTickRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    defect_run_id: int | None = Field(default=None, ge=1)


class ScanSpineTickEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    spine_tick_run_id: int
    defect_evidence_id: int | None = None
    tick_rank: int
    confidence_score: float
    severity_hint: ScanSpineTickSeverityHint | str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    angle_degrees: float
    edge_distance_px: int
    spine_overlap_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSpineTickArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    spine_tick_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanSpineTickIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    spine_tick_run_id: int
    issue_type: str
    severity: ScanSpineTickIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSpineTickHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    spine_tick_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSpineTickRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    defect_run_id: int
    source_checksum: str
    spine_tick_checksum: str
    detection_status: ScanSpineTickStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanSpineTickRunDetail(ScanSpineTickRunRead):
    evidence: list[ScanSpineTickEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanSpineTickArtifactRead] = Field(default_factory=list)
    issues: list[ScanSpineTickIssueRead] = Field(default_factory=list)
    history: list[ScanSpineTickHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    source_preview_data_url: str | None = None
    spine_region_preview_data_url: str | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ScanSpineTickRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSpineTickRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    high_density_anomaly_count: int = 0


class ScanSpineTickEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSpineTickEvidenceRead]
    total_items: int
    limit: int
    offset: int
    severity_hint_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0


class ScanSpineTickIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSpineTickIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanSpineTickFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSpineTickRunRead]
    total_items: int
    limit: int
    offset: int
