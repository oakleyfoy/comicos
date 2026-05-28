from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationNotificationType = Literal[
    "SYSTEM_ALERT",
    "WORKFLOW_FAILURE",
    "DEAD_LETTER_ALERT",
    "REPLAY_WARNING",
    "REVIEW_REQUIRED",
    "AUTHENTICATION_WARNING",
    "MAINTENANCE_RESULT",
    "QUEUE_WARNING",
    "BATCH_FAILURE",
    "OPS_NOTIFICATION",
]
AutomationNotificationStatus = Literal["CREATED", "QUEUED", "DELIVERED", "FAILED", "ACKNOWLEDGED", "SUPPRESSED"]
AutomationDeliveryChannel = Literal["IN_APP", "EMAIL_FUTURE", "SMS_FUTURE", "OPS_CONSOLE", "WEBHOOK_FUTURE"]
AutomationDeliveryStatus = Literal["PENDING", "DELIVERED", "FAILED", "SKIPPED"]
AutomationAlertSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
AutomationAlertStatus = Literal["ACTIVE", "ACKNOWLEDGED", "ESCALATED", "RESOLVED", "SUPPRESSED"]


class AutomationNotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    notification_type: AutomationNotificationType | str
    source_event_type: str = Field(min_length=1, max_length=64)
    source_record_type: str | None = Field(default=None, max_length=64)
    source_record_id: int | None = None
    source_checksum: str | None = Field(default=None, max_length=64)
    notification_payload_json: dict[str, Any] = Field(default_factory=dict)
    replay_safe: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationNotificationArtifactRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: str
    storage_path: str
    artifact_checksum: str


class AutomationNotificationDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_id: int
    delivery_channel: AutomationDeliveryChannel | str
    delivery_status: AutomationDeliveryStatus | str
    delivery_rank: int
    destination_key: str
    attempted_at: datetime | None = None
    delivered_at: datetime | None = None
    failure_reason: str | None = None
    delivery_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationNotificationTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_key: str
    template_name: str
    template_category: str
    template_status: str
    subject_template: str
    body_template: str
    replay_safe: bool
    template_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationNotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    preference_key: str
    notification_type: str
    delivery_channel: str
    enabled: bool
    escalation_enabled: bool
    quiet_hours_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_key: str
    alert_type: str
    alert_severity: AutomationAlertSeverity | str
    alert_status: AutomationAlertStatus | str
    source_notification_id: int | None = None
    escalation_level: str
    alert_checksum: str
    replay_safe: bool
    metadata_json: dict[str, Any]
    created_at: datetime
    acknowledged_at: datetime | None = None


class AutomationNotificationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_id: int | None = None
    issue_type: str
    severity: AutomationAlertSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationNotificationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_id: int | None = None
    alert_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    notification_key: str
    notification_type: AutomationNotificationType | str
    notification_status: AutomationNotificationStatus | str
    source_event_type: str
    source_record_type: str | None = None
    source_record_id: int | None = None
    source_checksum: str | None = None
    notification_payload_json: dict[str, Any]
    notification_checksum: str
    replay_safe: bool
    created_at: datetime
    delivered_at: datetime | None = None
    metadata_json: dict[str, Any]
    rendered_subject: str | None = None
    rendered_body: str | None = None
    notification_manifest_json: dict[str, Any] = Field(default_factory=dict)
    deliveries: list[AutomationNotificationDeliveryRead] = Field(default_factory=list)
    alerts: list[AutomationAlertRead] = Field(default_factory=list)
    issues: list[AutomationNotificationIssueRead] = Field(default_factory=list)
    history: list[AutomationNotificationHistoryRead] = Field(default_factory=list)
    artifacts: list[AutomationNotificationArtifactRead] = Field(default_factory=list)


class AutomationNotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationNotificationRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    type_counts: dict[str, int] = Field(default_factory=dict)
    queued_count: int = 0
    failed_delivery_count: int = 0
    active_alert_count: int = 0
    critical_alert_count: int = 0


class AutomationAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationAlertRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)


class AutomationNotificationPreferenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationNotificationPreferenceRead]
    total_items: int
    limit: int
    offset: int


class AutomationNotificationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationNotificationIssueRead]
    total_items: int
    limit: int
    offset: int
    severity_counts: dict[str, int] = Field(default_factory=dict)


class AutomationNotificationDeliveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutomationNotificationDeliveryRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
