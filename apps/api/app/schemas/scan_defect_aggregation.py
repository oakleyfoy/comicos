from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanDefectAggregationStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanDefectAggregationSeverity = Literal["MINOR", "MODERATE", "MAJOR"]
ScanDefectAggregationIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanDefectAggregationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    defect_run_id: int | None = Field(default=None, ge=1)


class ScanDefectAggregateClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    aggregation_run_id: int
    cluster_rank: int
    cluster_type: str
    cluster_region: str
    cluster_confidence: float
    aggregate_severity_hint: ScanDefectAggregationSeverity | str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    cluster_area_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectAggregateEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    aggregation_run_id: int
    cluster_id: int
    source_detector: str
    source_evidence_id: int
    evidence_type: str
    confidence_score: float
    contribution_weight: float
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectAggregationArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    aggregation_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanDefectAggregationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    aggregation_run_id: int
    issue_type: str
    severity: ScanDefectAggregationIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectAggregationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    aggregation_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanDefectAggregationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    source_checksum: str
    aggregation_checksum: str
    aggregation_status: ScanDefectAggregationStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanDefectAggregationRunDetail(ScanDefectAggregationRunRead):
    clusters: list[ScanDefectAggregateClusterRead] = Field(default_factory=list)
    evidence: list[ScanDefectAggregateEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanDefectAggregationArtifactRead] = Field(default_factory=list)
    issues: list[ScanDefectAggregationIssueRead] = Field(default_factory=list)
    history: list[ScanDefectAggregationHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    spine_tick_checksum: str | None = None
    corner_edge_checksum: str | None = None
    surface_defect_checksum: str | None = None
    structural_damage_checksum: str | None = None
    source_preview_data_url: str | None = None
    region_summaries: dict[str, Any] = Field(default_factory=dict)


class ScanDefectAggregationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectAggregationRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_clusters: int = 0
    unresolved_issue_count: int = 0
    aggregate_anomaly_density: float = 0.0


class ScanDefectAggregateClusterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectAggregateClusterRead]
    total_items: int
    limit: int
    offset: int
    cluster_type_counts: dict[str, int] = Field(default_factory=dict)
    severity_hint_counts: dict[str, int] = Field(default_factory=dict)
    mixed_cluster_count: int = 0


class ScanDefectAggregateEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectAggregateEvidenceRead]
    total_items: int
    limit: int
    offset: int
    source_detector_counts: dict[str, int] = Field(default_factory=dict)


class ScanDefectAggregationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectAggregationIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanDefectAggregationFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanDefectAggregationRunRead]
    total_items: int
    limit: int
    offset: int
