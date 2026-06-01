from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NextIssue(SQLModel, table=True):
    __tablename__ = "next_issue"
    __table_args__ = (
        SAIndex("ix_next_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_next_issue_owner_series", "owner_user_id", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    current_issue: str = Field(max_length=32, nullable=False)
    next_issue: str = Field(max_length=32, nullable=False)
    confidence: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
