from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationScheduleType = Literal["ONE_TIME", "RECURRING", "INTERVAL", "EVENT_DRIVEN"]
AutomationScheduleStatus = Literal["ACTIVE", "PAUSED", "DISABLED", "COMPLETED"]
AutomationTriggerType = Literal[
    "SCAN_COMPLETED",
    "REVIEW_COMPLETED",
    "REPLAY_COMPLETED",
    "AUTHENTICATION_COMPLETED",
    "FEED_GENERATED",
    "JOB_FAILED",
    "MANUAL_TRIGGER",
    "SYSTEM_TRIGGER",
]
AutomationTriggerStatus = Literal["PENDING", "PROCESSED", "FAILED", "SKIPPED"]
AutomationWorkflowCategory = Literal[
    "SCAN_PIPELINE",
    "REVIEW_PIPELINE",
    "REPLAY_PIPELINE",
    "NOTIFICATION_PIPELINE",
    "MAINTENANCE_PIPELINE",
    "SYSTEM_PIPELINE",
]
AutomationWorkflowStatus = Literal["ACTIVE", "PAUSED", "DISABLED"]
AutomationWorkflowDependencyMode = Literal["STRICT_SEQUENCE", "PARALLEL_ALLOWED", "CONDITIONAL", "OPTIONAL"]
AutomationWorkflowExecutionStatus = Literal["CREATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"]
AutomationWorkflowSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_name: str = Field(min_length=1, max_length=160)
    schedule_type: AutomationScheduleType | str
    cron_expression: str | None = Field(default=None, max_length=120)
    interval_seconds: int | None = Field(default=None, ge=1)
    next_run_at: datetime | None = None
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    workflow_key: str | None = Field(default=None, max_length=120)


class AutomationTriggerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_type: AutomationTriggerType | str
    source_event_type: str = Field(min_length=1, max_length=80)
    source_record_type: str | None = Field(default=None, max_length=80)
    source_record_id: int | None = Field(default=None, ge=1)
    source_checksum: str | None = Field(default=None, max_length=64)
    trigger_payload_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    workflow_key: str | None = Field(default=None, max_length=120)


class AutomationScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    schedule_key: str
    schedule_name: str
    schedule_type: AutomationScheduleType | str
    schedule_status: AutomationScheduleStatus | str
    cron_expression: str | None = None
    interval_seconds: int | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    replay_safe: bool
    deterministic_ordering_enabled: bool
    schedule_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationTriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    trigger_key: str
    trigger_type: AutomationTriggerType | str
    trigger_status: AutomationTriggerStatus | str
    source_event_type: str
    source_record_type: str | None = None
    source_record_id: int | None = None
    source_checksum: str | None = None
    trigger_payload_json: dict[str, Any]
    trigger_checksum: str
    triggered_at: datetime
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    step_rank: int
    step_key: str
    job_type: str
    dependency_mode: AutomationWorkflowDependencyMode | str
    delay_seconds: int | None = None
    required_success: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkflowExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    trigger_id: int | None = None
    schedule_id: int | None = None
    execution_status: AutomationWorkflowExecutionStatus | str
    execution_checksum: str
    execution_manifest_json: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkflowIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    execution_id: int | None = None
    issue_type: str
    severity: AutomationWorkflowSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkflowHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    execution_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationWorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    workflow_key: str
    workflow_name: str
    workflow_status: AutomationWorkflowStatus | str
    workflow_category: AutomationWorkflowCategory | str
    replay_safe: bool
    deterministic_ordering_enabled: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    steps: list[AutomationWorkflowStepRead] = Field(default_factory=list)
    latest_execution: AutomationWorkflowExecutionRead | None = None
    blocked_step_count: int = 0
    pending_trigger_count: int = 0


class AutomationScheduleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationScheduleRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    type_counts: dict[str, int] = Field(default_factory=dict)


class AutomationTriggerListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationTriggerRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    type_counts: dict[str, int] = Field(default_factory=dict)
    pending_trigger_count: int = 0


class AutomationWorkflowListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkflowRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    blocked_workflow_count: int = 0
    failed_execution_count: int = 0


class AutomationWorkflowExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkflowExecutionRead]
    total_items: int
    limit: int
    offset: int
    execution_status_counts: dict[str, int] = Field(default_factory=dict)


class AutomationWorkflowHistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkflowHistoryRead]
    total_items: int
    limit: int
    offset: int


class AutomationWorkflowIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationWorkflowIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
