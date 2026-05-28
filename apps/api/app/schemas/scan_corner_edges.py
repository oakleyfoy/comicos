from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanCornerEdgeStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanCornerEdgeIssueSeverity = Literal["INFO", "WARNING", "ERROR"]
ScanCornerEdgeSeverityHint = Literal["MINOR", "MODERATE", "MAJOR"]


class ScanCornerEdgeRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    defect_run_id: int | None = Field(default=None, ge=1)


class ScanCornerEdgeEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    corner_edge_run_id: int
    defect_evidence_id: int | None = None
    evidence_rank: int
    evidence_type: str
    confidence_score: float
    severity_hint: ScanCornerEdgeSeverityHint | str
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    edge_distance_px: int
    corner_overlap_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanCornerEdgeArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    corner_edge_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanCornerEdgeIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    corner_edge_run_id: int
    issue_type: str
    severity: ScanCornerEdgeIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanCornerEdgeHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    corner_edge_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanCornerEdgeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    defect_run_id: int
    source_checksum: str
    corner_edge_checksum: str
    detection_status: ScanCornerEdgeStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanCornerEdgeRunDetail(ScanCornerEdgeRunRead):
    evidence: list[ScanCornerEdgeEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanCornerEdgeArtifactRead] = Field(default_factory=list)
    issues: list[ScanCornerEdgeIssueRead] = Field(default_factory=list)
    history: list[ScanCornerEdgeHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    source_preview_data_url: str | None = None
    corner_region_preview_data_url: str | None = None
    edge_region_preview_data_url: str | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ScanCornerEdgeRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanCornerEdgeRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    high_density_wear_count: int = 0


class ScanCornerEdgeEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanCornerEdgeEvidenceRead]
    total_items: int
    limit: int
    offset: int
    evidence_type_counts: dict[str, int] = Field(default_factory=dict)
    severity_hint_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0


class ScanCornerEdgeIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanCornerEdgeIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanCornerEdgeFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanCornerEdgeRunRead]
    total_items: int
    limit: int
    offset: int
