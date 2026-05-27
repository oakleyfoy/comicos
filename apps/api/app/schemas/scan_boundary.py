from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanBoundaryStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanBoundaryArtifactType = Literal[
    "BOUNDARY_OVERLAY",
    "COVER_BOX_PREVIEW",
    "BACKGROUND_MASK",
    "GEOMETRY_MANIFEST",
]
ScanBoundaryIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanBoundaryRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    normalization_run_id: int | None = Field(default=None, ge=1)


class ScanBoundaryArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    boundary_run_id: int
    scan_image_id: int
    artifact_type: ScanBoundaryArtifactType | str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    width_px: int
    height_px: int
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanBoundaryIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    boundary_run_id: int
    scan_image_id: int
    issue_type: str
    severity: ScanBoundaryIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanBoundaryHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    boundary_run_id: int
    scan_image_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanBoundaryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    normalization_run_id: int
    source_artifact_id: int
    source_checksum: str
    boundary_checksum: str
    boundary_status: ScanBoundaryStatus | str
    algorithm_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanBoundaryRunDetail(ScanBoundaryRunRead):
    artifacts: list[ScanBoundaryArtifactRead] = Field(default_factory=list)
    issues: list[ScanBoundaryIssueRead] = Field(default_factory=list)
    history: list[ScanBoundaryHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalized_source_checksum: str | None = None
    source_preview_data_url: str | None = None
    boundary_overlay_preview_data_url: str | None = None
    cover_box_preview_data_url: str | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float | None = None


class ScanBoundaryRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanBoundaryRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_run_count: int = 0
    unresolved_issue_count: int = 0


class ScanBoundaryIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanBoundaryIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanBoundaryFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanBoundaryRunRead]
    total_items: int
    limit: int
    offset: int


class ScanBoundaryArtifactReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact: ScanBoundaryArtifactRead
