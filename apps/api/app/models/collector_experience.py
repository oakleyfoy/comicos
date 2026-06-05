"""P65 Collector Experience Platform models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P65_SOURCE_VERSION = "P65"

TASK_TYPE_BUY = "BUY"
TASK_TYPE_SELL = "SELL"
TASK_TYPE_GRADE = "GRADE"
TASK_TYPE_ACQUIRE = "ACQUIRE"
TASK_TYPE_WATCH = "WATCH"
TASK_TYPE_REVIEW = "REVIEW"
TASK_TYPES = (TASK_TYPE_BUY, TASK_TYPE_SELL, TASK_TYPE_GRADE, TASK_TYPE_ACQUIRE, TASK_TYPE_WATCH, TASK_TYPE_REVIEW)

TASK_STATUS_NEW = "NEW"
TASK_STATUS_IN_PROGRESS = "IN_PROGRESS"
TASK_STATUS_COMPLETED = "COMPLETED"
TASK_STATUS_DISMISSED = "DISMISSED"

NOTIF_STATUS_UNREAD = "UNREAD"
NOTIF_STATUS_READ = "READ"
NOTIF_STATUS_ARCHIVED = "ARCHIVED"

DELIVERY_IN_APP = "IN_APP"
DELIVERY_EMAIL = "EMAIL"
DELIVERY_DIGEST = "DIGEST"

AUTOMATION_STATUS_SUCCESS = "SUCCESS"
AUTOMATION_STATUS_FAILED = "FAILED"
AUTOMATION_STATUS_RUNNING = "RUNNING"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CollectorTaskSnapshot(SQLModel, table=True):
    __tablename__ = "collector_task_snapshot"
    __table_args__ = (SAIndex("ix_collector_task_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    source_fingerprint_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P65_SOURCE_VERSION, max_length=16, nullable=False)


class CollectorTaskItem(SQLModel, table=True):
    __tablename__ = "collector_task_item"
    __table_args__ = (SAIndex("ix_collector_task_item_snap_type", "snapshot_id", "task_type", "status", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="collector_task_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    task_type: str = Field(max_length=16, nullable=False, index=True)
    status: str = Field(default=TASK_STATUS_NEW, max_length=16, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    priority_score: float = Field(default=0.0, nullable=False)
    source_system: str = Field(default="", max_length=32, nullable=False, index=True)
    source_ref_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))
    action_hint: str = Field(default="", max_length=64, nullable=False)
    status_history_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectorNarrativeSnapshot(SQLModel, table=True):
    __tablename__ = "collector_narrative_snapshot"
    __table_args__ = (SAIndex("ix_collector_narrative_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    week_start: str = Field(default="", max_length=16, nullable=False)
    readiness_status: str = Field(default="SUCCESS", max_length=16, nullable=False)
    briefing_markdown: str = Field(default="", sa_column=Column(Text, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P65_SOURCE_VERSION, max_length=16, nullable=False)


class CollectorNarrativeItem(SQLModel, table=True):
    __tablename__ = "collector_narrative_item"
    __table_args__ = (SAIndex("ix_collector_narrative_item_snap", "snapshot_id", "narrative_kind", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="collector_narrative_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    narrative_kind: str = Field(max_length=32, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    narrative_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    signal_citations_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class AutomationSubscription(SQLModel, table=True):
    __tablename__ = "automation_subscription"
    __table_args__ = (SAIndex("ix_automation_sub_owner_kind", "owner_user_id", "automation_kind", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    automation_kind: str = Field(max_length=32, nullable=False, index=True)
    delivery_type: str = Field(default=DELIVERY_IN_APP, max_length=16, nullable=False)
    enabled: bool = Field(default=True, nullable=False)
    config_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRun(SQLModel, table=True):
    __tablename__ = "automation_run"
    __table_args__ = (SAIndex("ix_automation_run_owner_started", "owner_user_id", "started_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    subscription_id: int | None = Field(default=None, foreign_key="automation_subscription.id", nullable=True)
    automation_kind: str = Field(max_length=32, nullable=False, index=True)
    delivery_type: str = Field(default=DELIVERY_IN_APP, max_length=16, nullable=False)
    status: str = Field(default=AUTOMATION_STATUS_SUCCESS, max_length=16, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class NotificationSnapshot(SQLModel, table=True):
    __tablename__ = "notification_snapshot"
    __table_args__ = (SAIndex("ix_notification_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    unread_count: int = Field(default=0, nullable=False)
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P65_SOURCE_VERSION, max_length=16, nullable=False)


class NotificationItem(SQLModel, table=True):
    __tablename__ = "notification_item"
    __table_args__ = (SAIndex("ix_notification_item_snap_status", "snapshot_id", "status", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="notification_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    notification_type: str = Field(max_length=32, nullable=False, index=True)
    status: str = Field(default=NOTIF_STATUS_UNREAD, max_length=16, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    deep_link: str = Field(default="", max_length=256, nullable=False)
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
