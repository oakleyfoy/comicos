from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanHistoricalComparisonStatus = Literal["PENDING", "COMPLETE", "FAILED", "INCONCLUSIVE"]
ScanHistoricalComparisonIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanHistoricalComparisonRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    reconciliation_run_id: int | None = Field(default=None, ge=1)
    visual_evidence_run_id: int | None = Field(default=None, ge=1)
    review_session_id: int | None = Field(default=None, ge=1)
    max_prior_scans: int = Field(default=3, ge=1, le=10)


class ScanHistoricalComparisonPairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    comparison_run_id: int
    current_scan_image_id: int
    prior_scan_image_id: int
    current_identity_key: str
    prior_identity_key: str
    match_basis: str
    match_confidence: float
    current_checksum: str
    prior_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanHistoricalComparisonDeltaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    comparison_run_id: int
    pair_id: int
    delta_rank: int
    delta_type: str
    delta_category: str
    delta_direction: str
    confidence_score: float
    severity_hint: str
    region_type: str | None = None
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanHistoricalComparisonArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    comparison_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanHistoricalComparisonIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    comparison_run_id: int
    issue_type: str
    severity: ScanHistoricalComparisonIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanHistoricalComparisonHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    comparison_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanHistoricalComparisonRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    reconciliation_run_id: int | None = None
    visual_evidence_run_id: int | None = None
    review_session_id: int | None = None
    source_checksum: str
    historical_comparison_checksum: str
    comparison_status: ScanHistoricalComparisonStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanHistoricalComparisonRunDetail(ScanHistoricalComparisonRunRead):
    pairs: list[ScanHistoricalComparisonPairRead] = Field(default_factory=list)
    deltas: list[ScanHistoricalComparisonDeltaRead] = Field(default_factory=list)
    artifacts: list[ScanHistoricalComparisonArtifactRead] = Field(default_factory=list)
    issues: list[ScanHistoricalComparisonIssueRead] = Field(default_factory=list)
    history: list[ScanHistoricalComparisonHistoryRead] = Field(default_factory=list)
    current_original_scan_checksum: str | None = None
    current_normalization_checksum: str | None = None
    current_boundary_checksum: str | None = None
    current_reconciliation_checksum: str | None = None
    current_aggregation_checksum: str | None = None
    current_grading_assistance_checksum: str | None = None
    current_review_checksum: str | None = None
    prior_lineage: list[dict[str, Any]] = Field(default_factory=list)
    current_preview_data_url: str | None = None
    side_by_side_preview_data_url: str | None = None
    delta_overlay_preview_data_url: str | None = None


class ScanHistoricalComparisonRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanHistoricalComparisonRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    inconclusive_count: int = 0
    scans_with_prior_history_count: int = 0


class ScanHistoricalComparisonPairListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanHistoricalComparisonPairRead]
    total_items: int
    limit: int
    offset: int
    match_basis_counts: dict[str, int] = Field(default_factory=dict)


class ScanHistoricalComparisonDeltaListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanHistoricalComparisonDeltaRead]
    total_items: int
    limit: int
    offset: int
    delta_type_counts: dict[str, int] = Field(default_factory=dict)
    delta_direction_counts: dict[str, int] = Field(default_factory=dict)


class ScanHistoricalComparisonIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanHistoricalComparisonIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)
