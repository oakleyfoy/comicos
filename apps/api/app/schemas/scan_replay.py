from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ScanReplayScope = Literal["SINGLE_SCAN", "FULL_P40_PIPELINE", "SELECTED_STAGE", "OPS_AUDIT", "BATCH_REPLAY"]
ScanReplayStatus = Literal["COMPLETE", "COMPLETE_WITH_WARNINGS", "FAILED", "CRITICAL", "REPLAY_BLOCKED"]
ScanReplayStepStatus = Literal["MATCHED", "MISMATCHED", "SKIPPED", "MISSING_SOURCE", "REPLAY_BLOCKED", "ERROR"]
ScanReplayCheckStatus = Literal["PASS", "FAIL", "WARNING", "SKIPPED"]
ScanReplaySeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class ScanReplayRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_image_id: int | None = Field(default=None, ge=1)
    replay_scope: ScanReplayScope | str = "FULL_P40_PIPELINE"
    selected_phase_key: str | None = None


class ScanReplayStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    step_rank: int
    phase_key: str
    source_record_id: int | None = None
    expected_checksum: str | None = None
    observed_checksum: str | None = None
    replay_step_status: ScanReplayStepStatus | str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReplayCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    step_id: int | None = None
    check_type: str
    check_status: ScanReplayCheckStatus | str
    expected_value: str | None = None
    observed_value: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReplayDiscrepancyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    step_id: int | None = None
    discrepancy_type: str
    severity: ScanReplaySeverity | str
    expected_value: str | None = None
    observed_value: str | None = None
    discrepancy_message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReplayArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    media_type: str | None = None
    text_preview: str | None = None
    body_base64: str | None = None
    created_at: datetime


class ScanReplayIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    issue_type: str
    severity: ScanReplaySeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReplayHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_run_id: int
    event_type: str
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class ScanReplayRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    scan_image_id: int | None = None
    replay_scope: ScanReplayScope | str
    source_checksum: str
    replay_checksum: str
    replay_status: ScanReplayStatus | str
    engine_version: str
    input_manifest_json: dict[str, Any]
    output_manifest_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class ScanReplayRunDetail(ScanReplayRunRead):
    steps: list[ScanReplayStepRead] = Field(default_factory=list)
    checks: list[ScanReplayCheckRead] = Field(default_factory=list)
    discrepancies: list[ScanReplayDiscrepancyRead] = Field(default_factory=list)
    artifacts: list[ScanReplayArtifactRead] = Field(default_factory=list)
    issues: list[ScanReplayIssueRead] = Field(default_factory=list)
    history: list[ScanReplayHistoryRead] = Field(default_factory=list)
    original_scan_checksum: str | None = None
    scan_feed_checksum: str | None = None
    lineage_chain: list[dict[str, Any]] = Field(default_factory=list)
    critical_discrepancy_count: int = 0


class ScanReplayRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReplayRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    critical_discrepancy_count: int = 0
    mismatch_count: int = 0


class ScanReplayStepListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReplayStepRead]
    total_items: int
    limit: int
    offset: int
    step_status_counts: dict[str, int] = Field(default_factory=dict)


class ScanReplayCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReplayCheckRead]
    total_items: int
    limit: int
    offset: int
    check_status_counts: dict[str, int] = Field(default_factory=dict)
    check_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanReplayDiscrepancyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReplayDiscrepancyRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
    discrepancy_type_counts: dict[str, int] = Field(default_factory=dict)


class ScanReplayIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanReplayIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
    issue_type_counts: dict[str, int] = Field(default_factory=dict)
