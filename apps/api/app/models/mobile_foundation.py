from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MobileDevice(SQLModel, table=True):
    __tablename__ = "mobile_devices"
    __table_args__ = (
        UniqueConstraint("organization_id", "device_identifier", name="uq_mobile_device_org_identifier"),
        SAIndex("ix_mobile_device_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_device_org_status_created", "organization_id", "device_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    device_identifier: str = Field(max_length=128, nullable=False, index=True)
    device_name: str = Field(max_length=200, nullable=False)
    device_type: str = Field(max_length=32, nullable=False, index=True)
    device_status: str = Field(max_length=24, nullable=False, index=True)
    last_seen_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileSession(SQLModel, table=True):
    __tablename__ = "mobile_sessions"
    __table_args__ = (
        SAIndex("ix_mobile_session_org_started", "organization_id", "started_at", "id"),
        SAIndex("ix_mobile_session_device_started", "device_id", "started_at", "id"),
        SAIndex("ix_mobile_session_org_status_started", "organization_id", "session_status", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    session_status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OfflineSyncContract(SQLModel, table=True):
    __tablename__ = "offline_sync_contracts"
    __table_args__ = (
        SAIndex("ix_offline_sync_contract_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_offline_sync_contract_org_type_created", "organization_id", "contract_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    contract_type: str = Field(max_length=32, nullable=False, index=True)
    contract_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileFoundationEvent(SQLModel, table=True):
    __tablename__ = "mobile_foundation_events"
    __table_args__ = (
        SAIndex("ix_mobile_foundation_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_foundation_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_mobile_foundation_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
