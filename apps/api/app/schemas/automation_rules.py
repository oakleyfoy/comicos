from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationRuleCategory = Literal["WORKFLOW", "RECOVERY", "NOTIFICATION", "QUEUE", "REVIEW", "AUTHENTICATION", "REPLAY", "OPS"]
AutomationRuleStatus = Literal["ACTIVE", "PAUSED", "DISABLED", "ARCHIVED"]
AutomationRuleVersionStatus = Literal["DRAFT", "ACTIVE", "SUPERSEDED", "ARCHIVED"]
AutomationRuleEvaluationType = Literal["WORKFLOW_TRIGGER", "QUEUE_RULE", "RECOVERY_RULE", "NOTIFICATION_RULE", "OPS_RULE", "SYSTEM_RULE"]
AutomationRuleEvaluationStatus = Literal["CREATED", "RUNNING", "MATCHED", "NOT_MATCHED", "FAILED", "SKIPPED"]
AutomationRuleActionType = Literal[
    "CREATE_JOB",
    "CREATE_NOTIFICATION",
    "CREATE_ALERT",
    "EXECUTE_WORKFLOW",
    "PAUSE_QUEUE",
    "RESUME_QUEUE",
    "CREATE_RECOVERY_RUN",
    "CREATE_BATCH_JOB",
    "ACKNOWLEDGE_ALERT",
    "REPLAY_VERIFY",
]
AutomationRuleActionStatus = Literal["CREATED", "EXECUTED", "FAILED", "SKIPPED", "BLOCKED"]
AutomationRuleSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    rule_key: str | None = Field(default=None, min_length=1, max_length=160)
    rule_name: str = Field(min_length=1, max_length=200)
    rule_category: AutomationRuleCategory | str
    rule_status: AutomationRuleStatus | str = "ACTIVE"
    condition_expression: str = Field(min_length=1, max_length=2048)
    action_definition_json: list[dict[str, Any]] = Field(default_factory=list)
    evaluation_scope: str = Field(default="system", min_length=1, max_length=80)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    replay_key: str = Field(min_length=1, max_length=120)


class AutomationRuleVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_status: AutomationRuleVersionStatus | str = "ACTIVE"
    condition_expression: str = Field(min_length=1, max_length=2048)
    action_definition_json: list[dict[str, Any]] = Field(default_factory=list)
    evaluation_scope: str = Field(default="system", min_length=1, max_length=80)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    replay_key: str = Field(min_length=1, max_length=120)


class AutomationRuleEvaluateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_version_id: int | None = Field(default=None, ge=1)
    evaluation_type: AutomationRuleEvaluationType | str
    evaluation_scope: str = Field(default="system", min_length=1, max_length=80)
    evaluation_input_json: dict[str, Any] = Field(default_factory=dict)
    evaluation_rank: int = Field(default=100, ge=1, le=100000)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    replay_key: str = Field(min_length=1, max_length=120)


class AutomationSystemRuleEvaluateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    evaluation_scope: str = Field(default="system", min_length=1, max_length=80)
    replay_key: str = Field(min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    rule_key: str
    rule_name: str
    rule_category: str
    rule_status: str
    current_version_id: int | None = None
    replay_safe: bool
    deterministic_ordering_enabled: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    version_number: int
    version_status: str
    condition_expression: str
    action_definition_json: list[dict[str, Any]]
    evaluation_scope: str
    replay_safe: bool
    version_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    rule_version_id: int
    evaluation_type: str
    evaluation_status: str
    evaluation_scope: str
    evaluation_input_json: dict[str, Any]
    evaluation_result_json: dict[str, Any]
    matched: bool
    evaluation_rank: int
    evaluation_checksum: str
    replay_safe: bool
    started_at: datetime
    completed_at: datetime | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_id: int
    action_type: str
    action_status: str
    action_rank: int
    target_scope: str
    action_payload_json: dict[str, Any]
    action_checksum: str
    replay_safe: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evaluation_id: int
    artifact_type: str
    storage_backend: str
    storage_path: str
    artifact_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    rule_version_id: int | None = None
    evaluation_id: int | None = None
    issue_type: str
    severity: AutomationRuleSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    rule_version_id: int | None = None
    evaluation_id: int | None = None
    action_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationRuleReadDetail(AutomationRuleRead):
    current_version: AutomationRuleVersionRead | None = None


class AutomationRuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    total_items: int
    limit: int
    offset: int
    active_rule_count: int = 0
    failed_evaluation_count: int = 0
    replay_drift_count: int = 0
    action_failure_count: int = 0
    paused_rule_count: int = 0
