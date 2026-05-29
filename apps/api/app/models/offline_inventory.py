from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OfflineInventoryRecord(SQLModel, table=True):
    __tablename__ = "offline_inventory_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "local_record_identifier", name="uq_offline_inventory_org_local_id"),
        SAIndex("ix_offline_inventory_record_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_offline_inventory_record_org_local_updated", "organization_id", "local_updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, nullable=True, index=True)
    local_record_identifier: str = Field(max_length=128, nullable=False, index=True)
    record_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    local_updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OfflineInventoryChange(SQLModel, table=True):
    __tablename__ = "offline_inventory_changes"
    __table_args__ = (
        SAIndex("ix_offline_inventory_change_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_offline_inventory_change_device_created", "device_id", "created_at", "id"),
        SAIndex("ix_offline_inventory_change_org_type_created", "organization_id", "change_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, nullable=True, index=True)
    change_type: str = Field(max_length=24, nullable=False, index=True)
    change_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OfflineSyncQueue(SQLModel, table=True):
    __tablename__ = "offline_sync_queue"
    __table_args__ = (
        SAIndex("ix_offline_sync_queue_org_queued", "organization_id", "queued_at", "id"),
        SAIndex("ix_offline_sync_queue_device_queued", "device_id", "queued_at", "id"),
        SAIndex("ix_offline_sync_queue_org_status_queued", "organization_id", "queue_status", "queued_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    queue_status: str = Field(max_length=24, nullable=False, index=True)
    queue_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    queued_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    processed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OfflineSyncConflict(SQLModel, table=True):
    __tablename__ = "offline_sync_conflicts"
    __table_args__ = (
        SAIndex("ix_offline_sync_conflict_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_offline_sync_conflict_org_status_created", "organization_id", "conflict_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, nullable=True, index=True)
    conflict_type: str = Field(max_length=32, nullable=False, index=True)
    local_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    server_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    conflict_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OfflineInventoryEvent(SQLModel, table=True):
    __tablename__ = "offline_inventory_events"
    __table_args__ = (
        SAIndex("ix_offline_inventory_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_offline_inventory_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_offline_inventory_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
