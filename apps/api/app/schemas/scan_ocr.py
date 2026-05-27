from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanOcrStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanOcrRegionType = Literal["TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE_BOX", "LOGO", "GENERIC_TEXT"]
ScanOcrCandidateType = Literal["TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE"]
ScanOcrIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanOcrRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    normalization_run_id: int | None = Field(default=None, ge=1)
    boundary_run_id: int | None = Field(default=None, ge=1)


class ScanOcrTextRegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ocr_run_id: int
    region_type: ScanOcrRegionType | str
    extracted_text: str
    normalized_text: str | None = None
    confidence_score: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    rotation_angle: float
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanOcrCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ocr_run_id: int
    candidate_type: ScanOcrCandidateType | str
    candidate_value: str
    normalized_candidate_value: str | None = None
    confidence_score: float
    source_region_id: int | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanOcrArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ocr_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanOcrIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ocr_run_id: int
    issue_type: str
    severity: ScanOcrIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanOcrHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ocr_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanOcrRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    normalization_run_id: int
    boundary_run_id: int
    source_artifact_id: int
    source_checksum: str
    ocr_checksum: str
    ocr_status: ScanOcrStatus | str
    ocr_engine: str
    ocr_engine_version: str | None = None
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanOcrRunDetail(ScanOcrRunRead):
    regions: list[ScanOcrTextRegionRead] = Field(default_factory=list)
    candidates: list[ScanOcrCandidateRead] = Field(default_factory=list)
    artifacts: list[ScanOcrArtifactRead] = Field(default_factory=list)
    issues: list[ScanOcrIssueRead] = Field(default_factory=list)
    history: list[ScanOcrHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    source_preview_data_url: str | None = None
    ocr_overlay_preview_data_url: str | None = None
    ocr_region_map_preview_data_url: str | None = None
    confidence_summary: dict[str, Any] = Field(default_factory=dict)


class ScanOcrRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanOcrRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    unresolved_issue_count: int = 0


class ScanOcrCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanOcrCandidateRead]
    total_items: int
    limit: int
    offset: int
    candidate_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanOcrIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanOcrIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanOcrFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanOcrRunRead]
    total_items: int
    limit: int
    offset: int
