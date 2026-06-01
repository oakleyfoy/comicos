from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FutureReleaseMatch(SQLModel, table=True):
    __tablename__ = "future_release_match"
    __table_args__ = (
        SAIndex("ix_future_release_match_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_future_release_match_owner_series", "owner_user_id", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    issue_number: str = Field(max_length=32, nullable=False)
    publisher: str = Field(max_length=120, nullable=False)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    variant_count: int = Field(default=0, nullable=False)
    confidence: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
