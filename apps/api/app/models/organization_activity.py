from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationActivityEvent(SQLModel, table=True):
    __tablename__ = "organization_activity_events"
    __table_args__ = (
        SAIndex("ix_org_activity_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_activity_event_org_type_created", "organization_id", "activity_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    activity_type: str = Field(max_length=64, nullable=False, index=True)
    activity_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    visibility_scope: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationNotification(SQLModel, table=True):
    __tablename__ = "organization_notifications"
    __table_args__ = (
        SAIndex("ix_org_notification_org_target_created", "organization_id", "target_user_id", "created_at", "id"),
        SAIndex("ix_org_notification_org_status_created", "organization_id", "notification_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    target_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    notification_type: str = Field(max_length=48, nullable=False, index=True)
    notification_title: str = Field(max_length=200, nullable=False)
    notification_body: str = Field(max_length=2000, nullable=False)
    notification_status: str = Field(max_length=24, nullable=False, index=True)
    activity_event_id: int | None = Field(default=None, foreign_key="organization_activity_events.id", nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationNotificationReceipt(SQLModel, table=True):
    __tablename__ = "organization_notification_receipts"
    __table_args__ = (
        UniqueConstraint(
            "organization_notification_id",
            "user_id",
            name="uq_org_notification_receipt_notification_user",
        ),
        SAIndex("ix_org_notification_receipt_user_created", "user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_notification_id: int = Field(foreign_key="organization_notifications.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    read_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
