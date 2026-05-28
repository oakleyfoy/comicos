from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationOpsSnapshotType = Literal[
    "SYSTEM_HEALTH",
    "WORKER_RUNTIME",
    "QUEUE_STATE",
    "RECOVERY_STATE",
    "BATCH_STATE",
    "NOTIFICATION_STATE",
    "REPLAY_STATE",
]
AutomationOpsSnapshotStatus = Literal["HEALTHY", "WARNING", "DEGRADED", "CRITICAL"]
AutomationOpsMetricCategory = Literal["QUEUE", "WORKER", "RECOVERY", "BATCH", "NOTIFICATION", "REPLAY", "STORAGE", "SYSTEM"]
AutomationOpsMetricStatus = Literal["NORMAL", "WARNING", "CRITICAL"]
AutomationOpsAuditType = Literal[
    "QUEUE_AUDIT",
    "WORKER_AUDIT",
    "REPLAY_AUDIT",
    "STORAGE_AUDIT",
    "CHECKSUM_AUDIT",
    "DEAD_LETTER_AUDIT",
    "NOTIFICATION_AUDIT",
]
AutomationOpsAuditStatus = Literal["PASS", "WARNING", "FAIL"]
AutomationOpsControlType = Literal[
    "PAUSE_QUEUE",
    "RESUME_QUEUE",
    "PAUSE_WORKFLOW",
    "RESUME_WORKFLOW",
    "ACKNOWLEDGE_ALERT",
    "ACKNOWLEDGE_FAILURE",
    "REPLAY_VERIFY",
    "MAINTENANCE_LOCK",
]
AutomationOpsControlStatus = Literal["CREATED", "APPLIED", "REJECTED", "EXPIRED"]
AutomationOpsSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationOpsSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    snapshot_type: AutomationOpsSnapshotType | str
    replay_key: str = Field(min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationOpsAuditRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    audit_type: AutomationOpsAuditType | str
    audit_scope: str = Field(default="system", min_length=1, max_length=80)
    snapshot_id: int | None = Field(default=None, ge=1)
    replay_key: str = Field(min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationOpsControlApplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    control_type: AutomationOpsControlType | str
    target_scope: str = Field(min_length=1, max_length=80)
    snapshot_id: int | None = Field(default=None, ge=1)
    replay_key: str = Field(min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationOpsSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    snapshot_key: str
    snapshot_type: str
    snapshot_status: str
    queue_depth: int
    active_workers: int
    active_workflows: int
    failed_jobs: int
    dead_letter_count: int
    replay_warning_count: int
    checksum_warning_count: int
    snapshot_checksum: str
    snapshot_manifest_json: dict[str, Any]
    replay_safe: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    metric_key: str
    metric_category: str
    metric_value: str
    metric_status: str
    metric_rank: int
    metric_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    snapshot_id: int | None = None
    audit_key: str
    audit_type: str
    audit_status: str
    audit_scope: str
    replay_safe: bool
    audit_checksum: str
    audit_result_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    snapshot_id: int | None = None
    control_key: str
    control_type: str
    control_status: str
    target_scope: str
    replay_safe: bool
    control_checksum: str
    control_snapshot_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    issue_type: str
    severity: AutomationOpsSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int | None = None
    audit_id: int | None = None
    control_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    audit_id: int | None = None
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationOpsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    total_items: int
    limit: int
    offset: int
    replay_warning_count: int = 0
    critical_issue_count: int = 0
    failed_audit_count: int = 0


class AutomationOpsSystemHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_status: str
    queue_depth: int
    active_workers: int
    failed_jobs: int
    dead_letter_count: int
    replay_warning_count: int
    checksum_warning_count: int
    critical_issue_count: int
    failed_audit_count: int
    latest_snapshot_id: int | None = None
    latest_snapshot_checksum: str | None = None
