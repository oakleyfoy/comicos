from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanSurfaceDefectStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanSurfaceDefectIssueSeverity = Literal["INFO", "WARNING", "ERROR"]
ScanSurfaceDefectSeverityHint = Literal["MINOR", "MODERATE", "MAJOR"]


class ScanSurfaceDefectRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    defect_run_id: int | None = Field(default=None, ge=1)


class ScanSurfaceDefectEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    surface_defect_run_id: int
    defect_evidence_id: int | None = None
    evidence_rank: int
    evidence_type: str
    evidence_category: str
    confidence_score: float
    severity_hint: ScanSurfaceDefectSeverityHint | str
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    surface_area_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSurfaceDefectArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    surface_defect_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanSurfaceDefectIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    surface_defect_run_id: int
    issue_type: str
    severity: ScanSurfaceDefectIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSurfaceDefectHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    surface_defect_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanSurfaceDefectRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    defect_run_id: int
    source_checksum: str
    surface_defect_checksum: str
    detection_status: ScanSurfaceDefectStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanSurfaceDefectRunDetail(ScanSurfaceDefectRunRead):
    evidence: list[ScanSurfaceDefectEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanSurfaceDefectArtifactRead] = Field(default_factory=list)
    issues: list[ScanSurfaceDefectIssueRead] = Field(default_factory=list)
    history: list[ScanSurfaceDefectHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    source_preview_data_url: str | None = None
    surface_region_preview_data_url: str | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ScanSurfaceDefectRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSurfaceDefectRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    high_density_surface_count: int = 0


class ScanSurfaceDefectEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSurfaceDefectEvidenceRead]
    total_items: int
    limit: int
    offset: int
    evidence_type_counts: dict[str, int] = Field(default_factory=dict)
    evidence_category_counts: dict[str, int] = Field(default_factory=dict)
    severity_hint_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0


class ScanSurfaceDefectIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSurfaceDefectIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanSurfaceDefectFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanSurfaceDefectRunRead]
    total_items: int
    limit: int
    offset: int
