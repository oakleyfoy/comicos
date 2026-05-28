from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanStructuralDamageStatus = Literal["PENDING", "COMPLETE", "FAILED"]
ScanStructuralDamageIssueSeverity = Literal["INFO", "WARNING", "ERROR"]
ScanStructuralDamageSeverityHint = Literal["MINOR", "MODERATE", "MAJOR"]


class ScanStructuralDamageRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    defect_run_id: int | None = Field(default=None, ge=1)


class ScanStructuralDamageEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    structural_damage_run_id: int
    defect_evidence_id: int | None = None
    evidence_rank: int
    evidence_type: str
    evidence_category: str
    confidence_score: float
    severity_hint: ScanStructuralDamageSeverityHint | str
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    structural_area_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanStructuralDamageArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    structural_damage_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanStructuralDamageIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    structural_damage_run_id: int
    issue_type: str
    severity: ScanStructuralDamageIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanStructuralDamageHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    structural_damage_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanStructuralDamageRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    defect_run_id: int
    source_checksum: str
    structural_damage_checksum: str
    detection_status: ScanStructuralDamageStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanStructuralDamageRunDetail(ScanStructuralDamageRunRead):
    evidence: list[ScanStructuralDamageEvidenceRead] = Field(default_factory=list)
    artifacts: list[ScanStructuralDamageArtifactRead] = Field(default_factory=list)
    issues: list[ScanStructuralDamageIssueRead] = Field(default_factory=list)
    history: list[ScanStructuralDamageHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    defect_checksum: str | None = None
    source_preview_data_url: str | None = None
    structural_region_preview_data_url: str | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ScanStructuralDamageRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanStructuralDamageRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0
    major_structural_count: int = 0


class ScanStructuralDamageEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanStructuralDamageEvidenceRead]
    total_items: int
    limit: int
    offset: int
    evidence_type_counts: dict[str, int] = Field(default_factory=dict)
    evidence_category_counts: dict[str, int] = Field(default_factory=dict)
    severity_hint_counts: dict[str, int] = Field(default_factory=dict)
    low_confidence_count: int = 0


class ScanStructuralDamageIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanStructuralDamageIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanStructuralDamageFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanStructuralDamageRunRead]
    total_items: int
    limit: int
    offset: int
