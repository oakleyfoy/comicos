from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class CollectionRun(SQLModel, table=True):
    __tablename__ = "collection_run"
    __table_args__ = (
        SAIndex("ix_collection_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_collection_run_publisher_series", "publisher", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(max_length=120, nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    first_issue_owned: str = Field(max_length=24, nullable=False)
    latest_issue_owned: str = Field(max_length=24, nullable=False)
    issue_count_owned: int = Field(nullable=False)
    continuity_status: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class CollectionContinuityAlert(SQLModel, table=True):
    __tablename__ = "collection_continuity_alert"
    __table_args__ = (
        SAIndex("ix_collection_continuity_alert_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_collection_continuity_alert_type_status", "alert_type", "alert_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    alert_type: str = Field(max_length=64, nullable=False, index=True)
    alert_status: str = Field(max_length=24, nullable=False, index=True)
    alert_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseWatchlist(SQLModel, table=True):
    __tablename__ = "release_watchlist"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "watchlist_name", "watchlist_type", name="uq_release_watchlist_owner_identity"),
        SAIndex("ix_release_watchlist_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    watchlist_name: str = Field(max_length=160, nullable=False)
    watchlist_type: str = Field(max_length=48, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseWatchlistItem(SQLModel, table=True):
    __tablename__ = "release_watchlist_item"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "publisher",
            "series_name",
            "character_name",
            "creator_name",
            "keyword",
            name="uq_release_watchlist_item_signature",
        ),
        SAIndex("ix_release_watchlist_item_watchlist_created", "watchlist_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    watchlist_id: int = Field(foreign_key="release_watchlist.id", nullable=False, index=True)
    publisher: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    series_name: str | None = Field(default=None, max_length=200, nullable=True, index=True)
    character_name: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    creator_name: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    keyword: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class ReleaseReminder(SQLModel, table=True):
    __tablename__ = "release_reminder"
    __table_args__ = (
        SAIndex("ix_release_reminder_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_release_reminder_type_date", "reminder_type", "reminder_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    reminder_type: str = Field(max_length=64, nullable=False, index=True)
    reminder_date: date = Field(nullable=False, index=True)
    reminder_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class WatchlistAgentExecution(SQLModel, table=True):
    __tablename__ = "watchlist_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_watchlist_agent_execution_uuid"),
        SAIndex("ix_watchlist_agent_execution_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_watchlist_agent_execution_agent_started", "agent_code", "started_at", "id"),
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
