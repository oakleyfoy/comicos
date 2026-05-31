from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_run_uuid() -> str:
    return str(uuid4())


class LunarFeedRun(SQLModel, table=True):
    __tablename__ = "lunar_feed_run"
    __table_args__ = (
        SAIndex("ix_lunar_feed_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_lunar_feed_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    run_uuid: str = Field(default_factory=generate_run_uuid, max_length=64, nullable=False, index=True)
    source_type: str = Field(max_length=24, nullable=False, index=True)
    file_name: str = Field(default="", max_length=260, nullable=False)
    file_period: str = Field(default="", max_length=32, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    records_processed: int = Field(default=0, nullable=False)
    records_created: int = Field(default=0, nullable=False)
    records_updated: int = Field(default=0, nullable=False)
    records_failed: int = Field(default=0, nullable=False)
    foc_alerts_created: int = Field(default=0, nullable=False)
    source_url: str = Field(default="", sa_column=Column(Text, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class LunarFeedRawRow(SQLModel, table=True):
    __tablename__ = "lunar_feed_raw_row"
    __table_args__ = (SAIndex("ix_lunar_feed_raw_row_run", "feed_run_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    feed_run_id: int = Field(foreign_key="lunar_feed_run.id", nullable=False, index=True)
    row_index: int = Field(default=0, nullable=False)
    product_code: str = Field(default="", max_length=64, nullable=False, index=True)
    row_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LunarFeedError(SQLModel, table=True):
    __tablename__ = "lunar_feed_error"
    __table_args__ = (SAIndex("ix_lunar_feed_error_run", "feed_run_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    feed_run_id: int = Field(foreign_key="lunar_feed_run.id", nullable=False, index=True)
    record_identifier: str = Field(default="", max_length=260, nullable=False)
    error_code: str = Field(max_length=64, nullable=False, index=True)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LunarFocAlert(SQLModel, table=True):
    __tablename__ = "lunar_foc_alert"
    __table_args__ = (SAIndex("ix_lunar_foc_alert_owner_foc", "owner_user_id", "foc_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    feed_run_id: int = Field(foreign_key="lunar_feed_run.id", nullable=False, index=True)
    product_code: str = Field(max_length=64, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    alert_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
