from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_scheduled_run_uuid() -> str:
    return str(uuid4())


class LunarScheduleConfig(SQLModel, table=True):
    __tablename__ = "lunar_schedule_config"
    __table_args__ = (
        SAIndex("ix_lunar_schedule_config_owner", "owner_user_id", unique=True),
        SAIndex("ix_lunar_schedule_config_next_run", "next_run_at", "enabled", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    enabled: bool = Field(default=True, nullable=False, index=True)
    schedule_type: str = Field(default="DAILY", max_length=24, nullable=False)
    schedule_time: str = Field(default="06:00", max_length=8, nullable=False)
    timezone: str = Field(default="America/Chicago", max_length=64, nullable=False)
    last_success_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_failure_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    next_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True, index=True))
    last_imported_file_name: str = Field(default="", max_length=260, nullable=False)
    last_imported_file_period: str = Field(default="", max_length=32, nullable=False)
    last_imported_checksum: str = Field(default="", max_length=64, nullable=False)
    last_imported_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LunarScheduledRun(SQLModel, table=True):
    __tablename__ = "lunar_scheduled_run"
    __table_args__ = (
        SAIndex("ix_lunar_scheduled_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_lunar_scheduled_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    run_uuid: str = Field(default_factory=generate_scheduled_run_uuid, max_length=64, nullable=False, index=True)
    trigger_type: str = Field(max_length=24, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    file_name: str | None = Field(default=None, max_length=260, nullable=True)
    file_period: str | None = Field(default=None, max_length=32, nullable=True)
    records_processed: int = Field(default=0, nullable=False)
    records_imported: int = Field(default=0, nullable=False)
    records_updated: int = Field(default=0, nullable=False)
    records_failed: int = Field(default=0, nullable=False)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class LunarScheduledRunError(SQLModel, table=True):
    __tablename__ = "lunar_scheduled_run_error"
    __table_args__ = (SAIndex("ix_lunar_scheduled_run_error_run", "scheduled_run_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    scheduled_run_id: int = Field(foreign_key="lunar_scheduled_run.id", nullable=False, index=True)
    error_code: str = Field(max_length=64, nullable=False, index=True)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
