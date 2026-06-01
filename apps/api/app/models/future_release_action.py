from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


FUTURE_RELEASE_ACTION_TYPES = (
    "PREORDER_NOW",
    "PREORDER_THIS_WEEK",
    "WATCH",
    "MISSED_FOC",
)


class FutureReleaseAction(SQLModel, table=True):
    __tablename__ = "future_release_action"
    __table_args__ = (
        SAIndex("ix_future_release_action_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_future_release_action_owner_series", "owner_user_id", "series_name", "id"),
        SAIndex("ix_future_release_action_type", "owner_user_id", "action_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    issue_number: str = Field(max_length=32, nullable=False)
    action_type: str = Field(max_length=24, nullable=False, index=True)
    priority_score: float = Field(nullable=False)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
