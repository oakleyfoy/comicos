from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationQueueCategory = Literal["SCAN_PIPELINE", "REPLAY", "NOTIFICATION", "MAINTENANCE", "BATCH", "REVIEW", "SYSTEM"]
AutomationQueueStatus = Literal["ACTIVE", "PAUSED", "DRAINING", "DISABLED"]
AutomationJobStatus = Literal["PENDING", "AVAILABLE", "RESERVED", "RUNNING", "COMPLETED", "FAILED", "RETRY_PENDING", "CANCELLED", "DEAD_LETTER"]
AutomationJobPriority = Literal["LOW", "NORMAL", "HIGH", "CRITICAL"]
AutomationAttemptStatus = Literal["STARTED", "SUCCEEDED", "FAILED", "ABANDONED", "TIMED_OUT"]
AutomationDependencyStatus = Literal["BLOCKING", "SATISFIED", "FAILED", "SKIPPED"]
AutomationIssueSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_key: str = Field(min_length=1, max_length=80)
    queue_name: str | None = Field(default=None, max_length=160)
    queue_category: AutomationQueueCategory | str = "SYSTEM"
    organization_id: int | None = Field(default=None, ge=1)
    parent_job_id: int | None = Field(default=None, ge=1)
    job_key: str = Field(min_length=1, max_length=160)
    job_type: str = Field(min_length=1, max_length=40)
    priority: AutomationJobPriority | str = "NORMAL"
    payload_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    source_record_type: str | None = Field(default=None, max_length=80)
    source_record_id: int | None = Field(default=None, ge=1)
    source_checksum: str | None = Field(default=None, min_length=1, max_length=64)
    available_at: datetime | None = None
    max_attempts: int = Field(default=1, ge=1, le=25)
    replay_safe: bool = True
    idempotency_key: str | None = Field(default=None, max_length=160)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationQueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    queue_key: str
    queue_name: str
    queue_category: AutomationQueueCategory | str
    queue_status: AutomationQueueStatus | str
    deterministic_ordering_enabled: bool
    max_concurrency: int
    metadata_json: dict[str, Any]
    created_at: datetime
    total_jobs: int = 0
    pending_jobs: int = 0
    failed_jobs: int = 0
    dead_letter_jobs: int = 0
    reserved_jobs: int = 0


class AutomationJobAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    attempt_number: int
    attempt_status: AutomationAttemptStatus | str
    worker_identifier: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    execution_time_ms: int | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationJobDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    depends_on_job_id: int
    dependency_status: AutomationDependencyStatus | str
    created_at: datetime


class AutomationJobArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    media_type: str | None = None
    text_preview: str | None = None
    body_base64: str | None = None
    created_at: datetime


class AutomationJobIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    issue_type: str
    severity: AutomationIssueSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationJobHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    queue_id: int
    parent_job_id: int | None = None
    job_key: str
    job_type: str
    job_status: AutomationJobStatus | str
    priority: AutomationJobPriority | str
    deterministic_rank: int
    payload_snapshot_json: dict[str, Any]
    payload_checksum: str
    source_record_type: str | None = None
    source_record_id: int | None = None
    source_checksum: str | None = None
    reservation_token: str | None = None
    reserved_until: datetime | None = None
    available_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    max_attempts: int
    current_attempt_count: int
    replay_safe: bool
    idempotency_key: str | None = None
    job_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime
    queue_key: str | None = None
    queue_name: str | None = None
    queue_status: str | None = None


class AutomationJobDetail(AutomationJobRead):
    attempts: list[AutomationJobAttemptRead] = Field(default_factory=list)
    dependencies: list[AutomationJobDependencyRead] = Field(default_factory=list)
    artifacts: list[AutomationJobArtifactRead] = Field(default_factory=list)
    issues: list[AutomationJobIssueRead] = Field(default_factory=list)
    history: list[AutomationJobHistoryRead] = Field(default_factory=list)
    dependency_graph: list[dict[str, Any]] = Field(default_factory=list)


class AutomationJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationJobRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    priority_counts: dict[str, int] = Field(default_factory=dict)
    queue_counts: dict[str, int] = Field(default_factory=dict)
    failed_job_count: int = 0
    dead_letter_count: int = 0
    reserved_job_count: int = 0


class AutomationQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationQueueRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    queue_category_counts: dict[str, int] = Field(default_factory=dict)


class AutomationJobAttemptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationJobAttemptRead]
    total_items: int
    limit: int
    offset: int


class AutomationJobHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationJobHistoryRead]
    total_items: int
    limit: int
    offset: int


class AutomationJobIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationJobIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
