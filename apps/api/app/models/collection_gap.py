from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


COLLECTION_GAP_TYPES = ("MISSING_ISSUE", "RUN_GAP", "KEY_MISSING", "MILESTONE_MISSING")
COLLECTION_GAP_PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class CollectionGap(SQLModel, table=True):
    __tablename__ = "collection_gap"
    __table_args__ = (
        SAIndex("ix_collection_gap_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_collection_gap_owner_status", "owner_user_id", "gap_type", "id"),
        SAIndex("ix_collection_gap_owner_priority", "owner_user_id", "priority", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(default="", max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    gap_type: str = Field(max_length=32, nullable=False, index=True)
    completion_percent: float = Field(nullable=False)
    priority: str = Field(max_length=16, nullable=False, index=True)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
