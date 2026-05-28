from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanVisualEvidenceStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanVisualEvidenceIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanVisualEvidenceRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    aggregation_run_id: int | None = Field(default=None, ge=1)
    grading_assistance_run_id: int | None = Field(default=None, ge=1)


class ScanVisualEvidencePackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    package_type: str
    package_status: str
    package_title: str
    package_summary: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanVisualEvidenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    package_id: int
    item_rank: int
    source_system: str
    source_record_id: int
    item_type: str
    item_title: str
    item_summary: str
    confidence_score: float
    severity_hint: str | None = None
    region_type: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanVisualEvidenceAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    item_id: int
    annotation_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    label: str
    confidence_score: float
    display_order: int
    style_hint: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanVisualEvidenceArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanVisualEvidenceIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    issue_type: str
    severity: ScanVisualEvidenceIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanVisualEvidenceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    visual_evidence_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanVisualEvidenceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    aggregation_run_id: int | None = None
    grading_assistance_run_id: int | None = None
    source_checksum: str
    visual_evidence_checksum: str
    evidence_status: ScanVisualEvidenceStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanVisualEvidenceRunDetail(ScanVisualEvidenceRunRead):
    packages: list[ScanVisualEvidencePackageRead] = Field(default_factory=list)
    items: list[ScanVisualEvidenceItemRead] = Field(default_factory=list)
    annotations: list[ScanVisualEvidenceAnnotationRead] = Field(default_factory=list)
    artifacts: list[ScanVisualEvidenceArtifactRead] = Field(default_factory=list)
    issues: list[ScanVisualEvidenceIssueRead] = Field(default_factory=list)
    history: list[ScanVisualEvidenceHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    reconciliation_checksum: str | None = None
    defect_checksum: str | None = None
    aggregation_checksum: str | None = None
    grading_assistance_checksum: str | None = None
    source_preview_data_url: str | None = None
    overlay_preview_data_url: str | None = None


class ScanVisualEvidenceRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidenceRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    incomplete_review_packet_count: int = 0
    low_confidence_package_count: int = 0


class ScanVisualEvidencePackageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidencePackageRead]
    total_items: int
    limit: int
    offset: int
    package_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanVisualEvidenceItemListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidenceItemRead]
    total_items: int
    limit: int
    offset: int
    source_system_counts: dict[str, int] = Field(default_factory=dict)


class ScanVisualEvidenceAnnotationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidenceAnnotationRead]
    total_items: int
    limit: int
    offset: int
    annotation_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanVisualEvidenceIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidenceIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanVisualEvidenceFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanVisualEvidenceRunRead]
    total_items: int
    limit: int
    offset: int
