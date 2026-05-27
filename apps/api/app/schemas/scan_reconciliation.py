from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanReconciliationStatus = Literal[
    "PENDING",
    "MATCH_CONFIRMED",
    "MATCH_PROBABLE",
    "MATCH_AMBIGUOUS",
    "NO_MATCH_FOUND",
    "MULTIPLE_HIGH_CONFIDENCE_MATCHES",
    "FAILED",
]
ScanReconciliationIssueSeverity = Literal["INFO", "WARNING", "ERROR"]


class ScanReconciliationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int = Field(ge=1)
    ocr_run_id: int | None = Field(default=None, ge=1)


class ScanReconciliationCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    reconciliation_run_id: int
    candidate_rank: int
    canonical_comic_id: int | None = None
    publisher: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    variant_description: str | None = None
    publication_date: str | None = None
    confidence_score: float
    title_similarity_score: float
    issue_similarity_score: float
    publisher_similarity_score: float
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReconciliationDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    reconciliation_run_id: int
    selected_candidate_id: int | None = None
    decision_status: str
    final_confidence_score: float
    decision_reason: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReconciliationArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    reconciliation_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    preview_data_url: str | None = None
    created_at: datetime


class ScanReconciliationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    reconciliation_run_id: int
    issue_type: str
    severity: ScanReconciliationIssueSeverity | str
    issue_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReconciliationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    reconciliation_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int
    normalization_run_id: int
    boundary_run_id: int
    ocr_run_id: int
    source_checksum: str
    reconciliation_checksum: str
    reconciliation_status: ScanReconciliationStatus | str
    reconciliation_engine_version: str
    canonical_dataset_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanReconciliationRunDetail(ScanReconciliationRunRead):
    candidates: list[ScanReconciliationCandidateRead] = Field(default_factory=list)
    decision: ScanReconciliationDecisionRead | None = None
    artifacts: list[ScanReconciliationArtifactRead] = Field(default_factory=list)
    issues: list[ScanReconciliationIssueRead] = Field(default_factory=list)
    history: list[ScanReconciliationHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    normalization_checksum: str | None = None
    boundary_checksum: str | None = None
    ocr_checksum: str | None = None
    source_preview_data_url: str | None = None
    selected_candidate: ScanReconciliationCandidateRead | None = None


class ScanReconciliationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReconciliationRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    ambiguous_match_count: int = 0
    low_confidence_count: int = 0


class ScanReconciliationCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReconciliationCandidateRead]
    total_items: int
    limit: int
    offset: int
    canonical_match_count: int = 0


class ScanReconciliationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReconciliationIssueRead]
    total_items: int
    limit: int
    offset: int
    issue_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanReconciliationFailureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReconciliationRunRead]
    total_items: int
    limit: int
    offset: int
