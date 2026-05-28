from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationBatchType = Literal[
    "REPLAY_SWEEP",
    "FEED_REBUILD",
    "AUTHENTICATION_RECHECK",
    "REVIEW_EXPORT",
    "INTEGRITY_AUDIT",
    "STORAGE_AUDIT",
    "CLEANUP_JOB",
    "SYSTEM_MAINTENANCE",
]
AutomationBatchStatus = Literal["CREATED", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "PARTIALLY_COMPLETED"]
AutomationBatchChunkStatus = Literal["CREATED", "RESERVED", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]
AutomationMaintenanceType = Literal[
    "CHECKSUM_AUDIT",
    "LINEAGE_AUDIT",
    "STORAGE_AUDIT",
    "ARTIFACT_CLEANUP",
    "REPLAY_AUDIT",
    "DEAD_LETTER_REVIEW",
    "QUEUE_INTEGRITY_CHECK",
    "SYSTEM_HEALTH_CHECK",
]
AutomationMaintenanceStatus = Literal["CREATED", "RUNNING", "COMPLETED", "FAILED", "BLOCKED"]
AutomationMaintenanceResultStatus = Literal["PASS", "WARNING", "FAIL"]
AutomationBatchSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationBatchRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    batch_type: AutomationBatchType | str
    source_scope: str = Field(min_length=1, max_length=80)
    item_ids: list[int] = Field(default_factory=list)
    chunk_size: int = Field(default=500, ge=1, le=5000)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationMaintenanceRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    maintenance_type: AutomationMaintenanceType | str
    maintenance_scope: str = Field(min_length=1, max_length=80)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationBatchArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_run_id: int | None = None
    maintenance_job_id: int | None = None
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationBatchIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_run_id: int | None = None
    maintenance_job_id: int | None = None
    issue_type: str
    severity: AutomationBatchSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationBatchHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_run_id: int | None = None
    maintenance_job_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationBatchChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_run_id: int
    chunk_rank: int
    chunk_status: AutomationBatchChunkStatus | str
    partition_key: str
    item_start: int
    item_end: int
    item_count: int
    chunk_checksum: str
    worker_execution_id: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationMaintenanceResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    maintenance_job_id: int
    result_type: str
    result_status: AutomationMaintenanceResultStatus | str
    result_snapshot_json: dict[str, Any]
    result_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationMaintenanceJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    maintenance_key: str
    maintenance_type: AutomationMaintenanceType | str
    maintenance_status: AutomationMaintenanceStatus | str
    maintenance_scope: str
    replay_safe: bool
    maintenance_checksum: str
    metadata_json: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    results: list[AutomationMaintenanceResultRead] = Field(default_factory=list)


class AutomationBatchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    batch_key: str
    batch_type: AutomationBatchType | str
    batch_status: AutomationBatchStatus | str
    source_scope: str
    deterministic_partitioning_enabled: bool
    replay_safe: bool
    total_item_count: int
    completed_item_count: int
    failed_item_count: int
    batch_checksum: str
    manifest_json: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    chunks: list[AutomationBatchChunkRead] = Field(default_factory=list)
    maintenance_jobs: list[AutomationMaintenanceJobRead] = Field(default_factory=list)
    artifacts: list[AutomationBatchArtifactRead] = Field(default_factory=list)
    issues: list[AutomationBatchIssueRead] = Field(default_factory=list)
    history: list[AutomationBatchHistoryRead] = Field(default_factory=list)


class AutomationBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationBatchRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    batch_type_counts: dict[str, int] = Field(default_factory=dict)
    failed_batch_count: int = 0
    maintenance_job_count: int = 0
    integrity_audit_count: int = 0


class AutomationBatchChunkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationBatchChunkRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class AutomationMaintenanceJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationMaintenanceJobRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    maintenance_type_counts: dict[str, int] = Field(default_factory=dict)


class AutomationMaintenanceResultListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationMaintenanceResultRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class AutomationBatchIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationBatchIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
