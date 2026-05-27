from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanDefectStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanDefectIssueSeverity = Literal["INFO", "WARNING", "ERROR"]
ScanDefectRegionType = Literal[
    "FULL_COVER",
    "SPINE_REGION",
    "TOP_EDGE",
    "BOTTOM_EDGE",
    "LEFT_EDGE",
    "RIGHT_EDGE",
    "TOP_LEFT_CORNER",
    "TOP_RIGHT_CORNER",
    "BOTTOM_LEFT_CORNER",
    "BOTTOM_RIGHT_CORNER",
    "CENTER_SURFACE",
    "TITLE_AREA",
    "PRICE_BOX_AREA",
]
ScanDefectEvidenceCategory = Literal[
    "EDGE_ANOMALY",
    "CORNER_ANOMALY",
    "SPINE_ANOMALY",
    "SURFACE_ANOMALY",
    "COLOR_ANOMALY",
    "CONTRAST_ANOMALY",
    "GEOMETRY_ANOMALY",
]


class ScanDefectRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    boundary_run_id: int | None = Field(default=None, ge=1)
    ocr_run_id: int | None = Field(default=None, ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)


class ScanDefectRegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    defect_run_id: int
    region_type: ScanDefectRegionType | str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    region_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    defect_run_id: int
    region_id: int
    evidence_type: str
    evidence_category: ScanDefectEvidenceCategory | str
    severity_hint: str
    confidence_score: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    defect_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanDefectIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    defect_run_id: int
    issue_type: str
    severity: ScanDefectIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    defect_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    normalization_run_id: int
    boundary_run_id: int
    ocr_run_id: int | None = None
    reconciliation_run_id: int | None = None
    source_artifact_id: int
    source_checksum: str
    defect_checksum: str
    defect_status: ScanDefectStatus | str
    detection_engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanDefectRunDetail(ScanDefectRunRead):
    regions: list[ScanDefectRegionRead] = Field(default_factory=list)
    evidence: list[ScanDefectEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanDefectArtifactRead] = Field(default_factory=list)
    issues: list[ScanDefectIssueRead] = Field(default_factory=list)
    history: list[ScanDefectHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    reconciliation_checksum: str | None = None
    source_preview_data_url: str | None = None
    quality_gates: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    quality_gate_counts: dict[str, int] = Field(default_factory=dict)


class ScanDefectRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    quality_gate_failure_count: int = 0
    low_confidence_evidence_count: int = 0


class ScanDefectRegionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectRegionRead]
    total_items: int
    limit: int
    offset: int
    region_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanDefectEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectEvidenceRead]
    total_items: int
    limit: int
    offset: int
    category_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0


class ScanDefectIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanDefectFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectRunRead]
    total_items: int
    limit: int
    offset: int
