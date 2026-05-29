from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MobileDeviceTrustState(SQLModel, table=True):
    __tablename__ = "mobile_device_trust_states"
    __table_args__ = (
        UniqueConstraint("organization_id", "mobile_device_id", name="uq_mobile_device_trust_org_device"),
        SAIndex("ix_mobile_device_trust_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_device_trust_org_status_updated", "organization_id", "trust_status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    mobile_device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    trust_status: str = Field(max_length=24, nullable=False, index=True)
    trust_reason: str | None = Field(default=None, max_length=255, nullable=True)
    trusted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    suspended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileDeviceSecurityPolicy(SQLModel, table=True):
    __tablename__ = "mobile_device_security_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "policy_key", name="uq_mobile_security_policy_org_key"),
        SAIndex("ix_mobile_security_policy_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_security_policy_org_status_updated", "organization_id", "policy_status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    policy_key: str = Field(max_length=64, nullable=False, index=True)
    policy_status: str = Field(max_length=16, nullable=False, index=True)
    policy_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileDeviceAccessLog(SQLModel, table=True):
    __tablename__ = "mobile_device_access_logs"
    __table_args__ = (
        SAIndex("ix_mobile_device_access_org_accessed", "organization_id", "accessed_at", "id"),
        SAIndex("ix_mobile_device_access_device_accessed", "mobile_device_id", "accessed_at", "id"),
        SAIndex("ix_mobile_device_access_org_result_accessed", "organization_id", "access_result", "accessed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    mobile_device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    access_result: str = Field(max_length=16, nullable=False, index=True)
    access_reason: str = Field(max_length=255, nullable=False)
    accessed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileDeviceSecurityEvent(SQLModel, table=True):
    __tablename__ = "mobile_device_security_events"
    __table_args__ = (
        SAIndex("ix_mobile_device_security_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_device_security_event_device_created", "mobile_device_id", "created_at", "id"),
        SAIndex("ix_mobile_device_security_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    mobile_device_id: int | None = Field(default=None, foreign_key="mobile_devices.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
