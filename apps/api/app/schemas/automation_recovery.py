from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationRetryMode = Literal["FIXED_DELAY", "LINEAR_BACKOFF", "EXPONENTIAL_BACKOFF", "MANUAL_ONLY"]
AutomationRecoveryType = Literal["RETRY", "DEAD_LETTER_TRANSFER", "LEASE_RECOVERY", "EXECUTION_RECOVERY", "REPLAY_RECOVERY", "MANUAL_RECOVERY"]
AutomationRecoveryStatus = Literal["CREATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"]
AutomationDeadLetterStatus = Literal["ACTIVE", "ACKNOWLEDGED", "REPLAY_PENDING", "RESOLVED", "ARCHIVED"]
AutomationFailureSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationRetryPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_name: str = Field(min_length=1, max_length=160)
    retry_mode: AutomationRetryMode | str
    max_attempts: int = Field(ge=1, le=25)
    base_delay_seconds: int = Field(ge=0, le=86400)
    max_delay_seconds: int = Field(ge=0, le=86400)
    deterministic_backoff_enabled: bool = True
    dead_letter_enabled: bool = True
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationRetryPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_key: str
    policy_name: str
    retry_mode: AutomationRetryMode | str
    max_attempts: int
    base_delay_seconds: int
    max_delay_seconds: int
    deterministic_backoff_enabled: bool
    dead_letter_enabled: bool
    replay_safe: bool
    policy_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRecoveryArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recovery_run_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRecoveryHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recovery_run_id: int
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRecoveryIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recovery_run_id: int
    issue_type: str
    severity: AutomationFailureSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationFailureEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int | None = None
    worker_execution_id: int | None = None
    failure_type: str
    failure_severity: AutomationFailureSeverity | str
    failure_snapshot_json: dict[str, Any]
    failure_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationDeadLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_job_id: int
    dead_letter_reason: str
    dead_letter_status: AutomationDeadLetterStatus | str
    failure_count: int
    source_checksum: str | None = None
    dead_letter_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRecoveryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    job_id: int
    worker_execution_id: int | None = None
    retry_policy_id: int | None = None
    recovery_status: AutomationRecoveryStatus | str
    recovery_type: AutomationRecoveryType | str
    recovery_rank: int
    recovery_checksum: str
    recovery_manifest_json: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    retry_policy: AutomationRetryPolicyRead | None = None
    dead_letter: AutomationDeadLetterRead | None = None
    failure_events: list[AutomationFailureEventRead] = Field(default_factory=list)
    artifacts: list[AutomationRecoveryArtifactRead] = Field(default_factory=list)
    issues: list[AutomationRecoveryIssueRead] = Field(default_factory=list)
    history: list[AutomationRecoveryHistoryRead] = Field(default_factory=list)


class AutomationRecoveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationRecoveryRunRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    recovery_type_counts: dict[str, int] = Field(default_factory=dict)
    dead_letter_count: int = 0
    critical_failure_count: int = 0


class AutomationDeadLetterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationDeadLetterRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class AutomationFailureEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationFailureEventRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)


class AutomationRecoveryIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationRecoveryIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
