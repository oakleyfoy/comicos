from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class ReleaseSeries(SQLModel, table=True):
    __tablename__ = "release_series"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "publisher",
            "series_name",
            "series_type",
            name="uq_release_series_owner_identity",
        ),
        SAIndex("ix_release_series_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_release_series_publisher_series", "publisher", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(max_length=120, nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    series_type: str = Field(max_length=48, nullable=False)
    status: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ReleaseIssue(SQLModel, table=True):
    __tablename__ = "release_issue"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "release_uuid", name="uq_release_issue_owner_uuid"),
        SAIndex("ix_release_issue_owner_release_date", "owner_user_id", "release_date", "id"),
        SAIndex("ix_release_issue_owner_foc_date", "owner_user_id", "foc_date", "id"),
        SAIndex("ix_release_issue_series_number", "series_id", "issue_number", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    series_id: int = Field(foreign_key="release_series.id", nullable=False, index=True)
    issue_number: str = Field(max_length=24, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    cover_price: float = Field(default=0.0, nullable=False)
    release_status: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseVariant(SQLModel, table=True):
    __tablename__ = "release_variant"
    __table_args__ = (
        UniqueConstraint("issue_id", "variant_name", "variant_type", name="uq_release_variant_identity"),
        UniqueConstraint("issue_id", "variant_uuid", name="uq_release_variant_uuid"),
        SAIndex("ix_release_variant_issue_created", "issue_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    variant_uuid: str = Field(default="", max_length=64, nullable=False, index=True)
    variant_name: str = Field(max_length=160, nullable=False)
    ratio_value: int | None = Field(default=None, nullable=True, index=True)
    ratio_type: str | None = Field(default=None, max_length=24, nullable=True)
    is_incentive_variant: bool = Field(default=False, nullable=False, index=True)
    variant_type: str = Field(max_length=48, nullable=False, index=True)
    cover_artist: str | None = Field(default=None, max_length=160, nullable=True)
    source_item_code: str = Field(default="", max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseKeySignal(SQLModel, table=True):
    __tablename__ = "release_key_signal"
    __table_args__ = (
        SAIndex("ix_release_key_signal_issue_type", "issue_id", "signal_type", "id"),
        SAIndex("ix_release_key_signal_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    signal_type: str = Field(max_length=64, nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    signal_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseAgentExecution(SQLModel, table=True):
    __tablename__ = "release_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_release_agent_execution_uuid"),
        SAIndex("ix_release_agent_execution_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_release_agent_execution_agent_started", "agent_code", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_code: str = Field(max_length=64, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
