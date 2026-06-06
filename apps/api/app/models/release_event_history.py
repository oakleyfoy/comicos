"""P74-01 release change records and event audit trail."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P74_SOURCE_VERSION = "p74-01"

P74_EVENT_DISCOVERED = "DISCOVERED"
P74_EVENT_UPDATED = "UPDATED"
P74_EVENT_VARIANT_ADDED = "VARIANT_ADDED"
P74_EVENT_RELEASE_DATE_CHANGED = "RELEASE_DATE_CHANGED"
P74_EVENT_REMOVED = "REMOVED"
P74_EVENT_RESTORED = "RESTORED"

P74_ALL_EVENT_TYPES = frozenset(
    {
        P74_EVENT_DISCOVERED,
        P74_EVENT_UPDATED,
        P74_EVENT_VARIANT_ADDED,
        P74_EVENT_RELEASE_DATE_CHANGED,
        P74_EVENT_REMOVED,
        P74_EVENT_RESTORED,
    }
)

P74_CHANGE_NEW_ISSUE = "NEW_ISSUE"
P74_CHANGE_NEW_VARIANT = "NEW_VARIANT"
P74_CHANGE_RELEASE_DATE = "RELEASE_DATE_CHANGE"
P74_CHANGE_PUBLISHER = "PUBLISHER_CHANGE"
P74_CHANGE_COVER = "COVER_CHANGE"
P74_CHANGE_METADATA = "METADATA_CHANGE"
P74_CHANGE_REMOVED = "REMOVED"
P74_CHANGE_RESTORED = "RESTORED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P74ReleaseChangeRecord(SQLModel, table=True):
    __tablename__ = "p74_release_change_record"
    __table_args__ = (
        SAIndex("ix_p74_release_change_owner_detected", "owner_user_id", "detected_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    variant_id: int | None = Field(default=None, foreign_key="release_variant.id", nullable=True, index=True)
    change_type: str = Field(max_length=48, nullable=False, index=True)
    before_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    after_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class P74ReleaseEventHistory(SQLModel, table=True):
    __tablename__ = "p74_release_event_history"
    __table_args__ = (
        SAIndex("ix_p74_release_event_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_p74_release_event_issue_type", "issue_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    variant_id: int | None = Field(default=None, foreign_key="release_variant.id", nullable=True, index=True)
    event_type: str = Field(max_length=48, nullable=False, index=True)
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
