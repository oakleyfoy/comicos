from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationNotification(SQLModel, table=True):
    __tablename__ = "automation_notifications"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "notification_key", name="uq_automation_notification_owner_key"),
        SAIndex("ix_automation_notification_status_created", "notification_status", "created_at", "id"),
        SAIndex("ix_automation_notification_type_created", "notification_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    notification_key: str = Field(max_length=120, nullable=False, index=True)
    notification_type: str = Field(max_length=40, nullable=False, index=True)
    notification_status: str = Field(max_length=24, nullable=False, index=True)
    source_event_type: str = Field(max_length=64, nullable=False, index=True)
    source_record_type: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    source_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    notification_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    notification_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    delivered_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class AutomationNotificationDelivery(SQLModel, table=True):
    __tablename__ = "automation_notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "delivery_channel", "destination_key", name="uq_automation_notification_delivery_dest"),
        SAIndex("ix_automation_notification_delivery_rank", "notification_id", "delivery_rank", "created_at", "id"),
        SAIndex("ix_automation_notification_delivery_status_created", "delivery_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    notification_id: int = Field(foreign_key="automation_notifications.id", nullable=False, index=True)
    delivery_channel: str = Field(max_length=32, nullable=False, index=True)
    delivery_status: str = Field(max_length=24, nullable=False, index=True)
    delivery_rank: int = Field(nullable=False, index=True)
    destination_key: str = Field(max_length=160, nullable=False, index=True)
    attempted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    delivered_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    failure_reason: str | None = Field(default=None, max_length=512, nullable=True)
    delivery_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationNotificationTemplate(SQLModel, table=True):
    __tablename__ = "automation_notification_templates"
    __table_args__ = (
        UniqueConstraint("template_key", name="uq_automation_notification_template_key"),
        SAIndex("ix_automation_notification_template_category_created", "template_category", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    template_key: str = Field(max_length=120, nullable=False, index=True)
    template_name: str = Field(max_length=160, nullable=False)
    template_category: str = Field(max_length=24, nullable=False, index=True)
    template_status: str = Field(max_length=24, nullable=False, index=True)
    subject_template: str = Field(max_length=512, nullable=False)
    body_template: str = Field(max_length=4096, nullable=False)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    template_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationNotificationPreference(SQLModel, table=True):
    __tablename__ = "automation_notification_preferences"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "preference_key", name="uq_automation_notification_preference_owner_key"),
        SAIndex("ix_automation_notification_preference_type_channel", "notification_type", "delivery_channel", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    preference_key: str = Field(max_length=120, nullable=False, index=True)
    notification_type: str = Field(max_length=40, nullable=False, index=True)
    delivery_channel: str = Field(max_length=32, nullable=False, index=True)
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    escalation_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    quiet_hours_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAlert(SQLModel, table=True):
    __tablename__ = "automation_alerts"
    __table_args__ = (
        UniqueConstraint("alert_key", name="uq_automation_alert_key"),
        SAIndex("ix_automation_alert_status_created", "alert_status", "created_at", "id"),
        SAIndex("ix_automation_alert_severity_created", "alert_severity", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    alert_key: str = Field(max_length=120, nullable=False, index=True)
    alert_type: str = Field(max_length=40, nullable=False, index=True)
    alert_severity: str = Field(max_length=16, nullable=False, index=True)
    alert_status: str = Field(max_length=24, nullable=False, index=True)
    source_notification_id: int | None = Field(default=None, foreign_key="automation_notifications.id", nullable=True, index=True)
    escalation_level: str = Field(max_length=16, nullable=False, index=True)
    alert_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AutomationNotificationIssue(SQLModel, table=True):
    __tablename__ = "automation_notification_issues"
    __table_args__ = (
        UniqueConstraint("notification_id", "issue_checksum", name="uq_automation_notification_issue_checksum"),
        SAIndex("ix_automation_notification_issue_notification_created", "notification_id", "created_at", "id"),
        SAIndex("ix_automation_notification_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    notification_id: int | None = Field(default=None, foreign_key="automation_notifications.id", nullable=True, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationNotificationHistory(SQLModel, table=True):
    __tablename__ = "automation_notification_history"
    __table_args__ = (
        UniqueConstraint("notification_id", "event_checksum", name="uq_automation_notification_history_checksum"),
        SAIndex("ix_automation_notification_history_notification_created", "notification_id", "created_at", "id"),
        SAIndex("ix_automation_notification_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    notification_id: int | None = Field(default=None, foreign_key="automation_notifications.id", nullable=True, index=True)
    alert_id: int | None = Field(default=None, foreign_key="automation_alerts.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
