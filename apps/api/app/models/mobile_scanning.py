from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanCapture(SQLModel, table=True):
    __tablename__ = "scan_captures"
    __table_args__ = (
        SAIndex("ix_scan_capture_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_scan_capture_device_created", "device_id", "created_at", "id"),
        SAIndex("ix_scan_capture_org_status_created", "organization_id", "scan_status", "created_at", "id"),
        SAIndex("ix_scan_capture_org_normalized", "organization_id", "normalized_value", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    device_id: int = Field(foreign_key="mobile_devices.id", nullable=False, index=True)
    scan_type: str = Field(max_length=32, nullable=False, index=True)
    scan_value: str = Field(max_length=512, nullable=False)
    normalized_value: str = Field(max_length=512, nullable=False, index=True)
    scan_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanLookupResult(SQLModel, table=True):
    __tablename__ = "scan_lookup_results"
    __table_args__ = (
        SAIndex("ix_scan_lookup_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_scan_lookup_capture_created", "scan_capture_id", "created_at", "id"),
        SAIndex("ix_scan_lookup_org_type_created", "organization_id", "lookup_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    scan_capture_id: int = Field(foreign_key="scan_captures.id", nullable=False, index=True)
    lookup_type: str = Field(max_length=32, nullable=False, index=True)
    lookup_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IntakeStagingRecord(SQLModel, table=True):
    __tablename__ = "intake_staging_records"
    __table_args__ = (
        SAIndex("ix_intake_staging_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_intake_staging_capture_created", "scan_capture_id", "created_at", "id"),
        SAIndex("ix_intake_staging_org_status_created", "organization_id", "staging_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    scan_capture_id: int = Field(foreign_key="scan_captures.id", nullable=False, index=True)
    staging_status: str = Field(max_length=24, nullable=False, index=True)
    staging_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanEvent(SQLModel, table=True):
    __tablename__ = "scan_events"
    __table_args__ = (
        SAIndex("ix_scan_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_scan_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_scan_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
