from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ScanNormalizationStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanNormalizationOrientation = Literal["portrait", "rotated_left", "rotated_right", "upside_down"]
ScanNormalizationArtifactType = Literal[
    "ROTATED",
    "CROPPED",
    "PERSPECTIVE_FIXED",
    "COLOR_NORMALIZED",
    "FINAL_NORMALIZED",
    "THUMBNAIL",
]
ScanNormalizationIssueType = Literal[
    "LOW_DPI",
    "EXCESSIVE_SKEW",
    "EXTREME_SHADOW",
    "OVEREXPOSED",
    "UNDEREXPOSED",
    "PARTIAL_SCAN",
    "BORDER_CLIPPING",
]


class ScanNormalizationRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)


class ScanNormalizationArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_normalization_run_id: int
    owner_user_id: int
    scan_image_id: int
    parent_artifact_id: int | None = None
    artifact_type: ScanNormalizationArtifactType | str
    artifact_order: int
    storage_backend: str
    storage_path: str
    width: int
    height: int
    dpi_x: int | None = None
    dpi_y: int | None = None
    artifact_checksum: str
    parent_checksum: str | None = None
    normalization_status: ScanNormalizationStatus | str
    metadata_json: dict
    preview_data_url: str | None = None
    created_at: datetime


class ScanNormalizationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_normalization_run_id: int
    owner_user_id: int
    scan_image_id: int
    issue_type: ScanNormalizationIssueType | str
    severity: str
    normalization_status: ScanNormalizationStatus | str
    metric_value: str | None = None
    detail_json: dict
    created_at: datetime


class ScanNormalizationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_normalization_run_id: int
    owner_user_id: int
    scan_image_id: int
    history_order: int
    stage_name: str
    event_type: str
    from_checksum: str | None = None
    to_checksum: str | None = None
    detail_json: dict
    notes: str | None = None
    created_at: datetime


class ScanNormalizationRunSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    source_sha256_checksum: str
    normalization_checksum: str
    normalization_status: ScanNormalizationStatus | str
    orientation_code: ScanNormalizationOrientation | str
    rotation_degrees: int
    crop_left: int
    crop_top: int
    crop_right: int
    crop_bottom: int
    perspective_strength: int
    issue_count: int
    artifact_count: int
    replayed_from_run_id: int | None = None
    final_artifact_id: int | None = None
    summary_json: dict
    created_at: datetime
    completed_at: datetime | None = None


class ScanNormalizationRunRead(ScanNormalizationRunSummaryRead):
    artifacts: list[ScanNormalizationArtifactRead] = Field(default_factory=list)
    issues: list[ScanNormalizationIssueRead] = Field(default_factory=list)
    history: list[ScanNormalizationHistoryRead] = Field(default_factory=list)
    source_preview_data_url: str | None = None
    final_preview_data_url: str | None = None


class ScanNormalizationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanNormalizationRunSummaryRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    replay_safe_run_count: int = 0


class ScanNormalizationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanNormalizationIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanNormalizationFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanNormalizationRunSummaryRead]
    total_items: int
    limit: int
    offset: int
