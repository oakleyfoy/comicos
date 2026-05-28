from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanGradingAssistanceStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanGradingAssistanceCategoryStatus = Literal["STRONG", "ACCEPTABLE", "LIMITED", "REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"]
ScanGradingAssistanceIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanGradingAssistanceRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    aggregation_run_id: int | None = Field(default=None, ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)


class ScanGradingAssistanceCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    grading_assistance_run_id: int
    category_type: str
    category_status: ScanGradingAssistanceCategoryStatus | str
    suggested_range_low: float
    suggested_range_high: float
    confidence_score: float
    evidence_count: int
    summary_text: str
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanGradingAssistanceFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    grading_assistance_run_id: int
    category_id: int
    source_cluster_id: int | None = None
    source_detector: str
    finding_type: str
    finding_severity_hint: str
    confidence_score: float
    grade_pressure_hint: str
    finding_text: str
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanGradingAssistanceArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    grading_assistance_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanGradingAssistanceIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    grading_assistance_run_id: int
    issue_type: str
    severity: ScanGradingAssistanceIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanGradingAssistanceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    grading_assistance_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanGradingAssistanceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    aggregation_run_id: int
    reconciliation_run_id: int | None = None
    source_checksum: str
    grading_assistance_checksum: str
    assistance_status: ScanGradingAssistanceStatus | str
    engine_version: str
    rubric_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanGradingAssistanceRunDetail(ScanGradingAssistanceRunRead):
    categories: list[ScanGradingAssistanceCategoryRead] = Field(default_factory=list)
    findings: list[ScanGradingAssistanceFindingRead] = Field(default_factory=list)
    artifacts: list[ScanGradingAssistanceArtifactRead] = Field(default_factory=list)
    issues: list[ScanGradingAssistanceIssueRead] = Field(default_factory=list)
    history: list[ScanGradingAssistanceHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    spine_tick_checksum: str | None = None
    corner_edge_checksum: str | None = None
    surface_defect_checksum: str | None = None
    structural_damage_checksum: str | None = None
    aggregation_checksum: str | None = None
    reconciliation_checksum: str | None = None
    source_preview_data_url: str | None = None
    overall_support: dict[str, Any] = Field(default_factory=dict)
    review_flags: list[dict[str, Any]] = Field(default_factory=list)


class ScanGradingAssistanceRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanGradingAssistanceRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    review_required_count: int = 0
    low_confidence_support_count: int = 0


class ScanGradingAssistanceCategoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanGradingAssistanceCategoryRead]
    total_items: int
    limit: int
    offset: int
    category_type_counts: dict[str, int] = Field(default_factory=dict)
    category_status_counts: dict[str, int] = Field(default_factory=dict)


class ScanGradingAssistanceFindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanGradingAssistanceFindingRead]
    total_items: int
    limit: int
    offset: int
    finding_type_counts: dict[str, int] = Field(default_factory=dict)
    grade_pressure_hint_counts: dict[str, int] = Field(default_factory=dict)


class ScanGradingAssistanceIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanGradingAssistanceIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanGradingAssistanceFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanGradingAssistanceRunRead]
    total_items: int
    limit: int
    offset: int
