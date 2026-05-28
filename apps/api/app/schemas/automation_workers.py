from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationWorkerType = Literal["API_WORKER", "SCAN_WORKER", "REPLAY_WORKER", "MAINTENANCE_WORKER", "SYSTEM_WORKER"]
AutomationWorkerStatus = Literal["STARTING", "IDLE", "RESERVED", "RUNNING", "PAUSED", "SHUTTING_DOWN", "OFFLINE", "ERROR"]
AutomationHeartbeatStatus = Literal["HEALTHY", "DEGRADED", "OVERLOADED", "LOST"]
AutomationLeaseStatus = Literal["ACTIVE", "RELEASED", "EXPIRED", "CONFLICTED"]
AutomationExecutionStatus = Literal["RESERVED", "STARTED", "RUNNING", "COMPLETED", "FAILED", "TIMED_OUT", "ABANDONED"]
AutomationWorkerSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationWorkerRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_identifier: str = Field(min_length=1, max_length=160)
    worker_type: AutomationWorkerType | str
    process_identifier: str | None = Field(default=None, max_length=80)
    hostname: str | None = Field(default=None, max_length=160)
    queue_scope_json: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(default=1, ge=1, le=25)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationWorkerHeartbeatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heartbeat_status: AutomationHeartbeatStatus | str = "HEALTHY"
    active_job_count: int = Field(default=0, ge=0)
    memory_usage_mb: int | None = Field(default=None, ge=0)
    cpu_usage_percent: float | None = Field(default=None, ge=0, le=100)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationWorkerLeaseAcquire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_token: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class AutomationWorkerLeaseRenew(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_token: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class AutomationWorkerExecutionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_token: str = Field(min_length=1, max_length=128)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationWorkerExecutionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_token: str = Field(min_length=1, max_length=128)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationWorkerExecutionFail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_token: str = Field(min_length=1, max_length=128)
    failure_reason: str = Field(min_length=1, max_length=1024)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationWorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_key: str
    worker_identifier: str
    worker_type: AutomationWorkerType | str
    worker_status: AutomationWorkerStatus | str
    process_identifier: str | None = None
    hostname: str | None = None
    queue_scope_json: dict[str, Any]
    current_job_id: int | None = None
    max_concurrency: int
    last_heartbeat_at: datetime | None = None
    startup_at: datetime
    shutdown_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    active_lease_count: int = 0
    active_execution_count: int = 0
    stale: bool = False
    heartbeat_age_seconds: int | None = None


class AutomationWorkerHeartbeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    heartbeat_status: AutomationHeartbeatStatus | str
    active_job_count: int
    memory_usage_mb: int | None = None
    cpu_usage_percent: float | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkerLeaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    job_id: int
    reservation_token: str
    lease_status: AutomationLeaseStatus | str
    lease_expires_at: datetime
    acquired_at: datetime
    released_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkerExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    job_id: int
    execution_status: AutomationExecutionStatus | str
    execution_rank: int
    started_at: datetime
    completed_at: datetime | None = None
    execution_time_ms: int | None = None
    execution_snapshot_json: dict[str, Any]
    execution_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkerIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    job_id: int | None = None
    issue_type: str
    severity: AutomationWorkerSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkerHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    worker_id: int
    job_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkerDetail(AutomationWorkerRead):
    heartbeats: list[AutomationWorkerHeartbeatRead] = Field(default_factory=list)
    leases: list[AutomationWorkerLeaseRead] = Field(default_factory=list)
    executions: list[AutomationWorkerExecutionRead] = Field(default_factory=list)
    issues: list[AutomationWorkerIssueRead] = Field(default_factory=list)
    history: list[AutomationWorkerHistoryRead] = Field(default_factory=list)


class AutomationWorkerListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkerRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    worker_type_counts: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    active_execution_count: int = 0
    runtime_issue_count: int = 0


class AutomationWorkerExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkerExecutionRead]
    total_items: int
    limit: int
    offset: int
    execution_status_counts: dict[str, int] = Field(default_factory=dict)


class AutomationWorkerHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkerHistoryRead]
    total_items: int
    limit: int
    offset: int


class AutomationWorkerIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkerIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)


class AutomationWorkerLeaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkerLeaseRead]
    total_items: int
    limit: int
    offset: int
