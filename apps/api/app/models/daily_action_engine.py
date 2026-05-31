from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


DAILY_ACTION_TYPES = (
    "PREORDER",
    "ACQUIRE",
    "GRADE",
    "SELL",
    "REBALANCE",
    "REVIEW",
    "WATCH",
)


class DailyCollectorAction(SQLModel, table=True):
    __tablename__ = "daily_collector_action"
    __table_args__ = (
        SAIndex(
            "ix_daily_collector_action_owner_type_title",
            "owner_user_id",
            "action_type",
            "title",
            "created_at",
            "id",
        ),
        SAIndex("ix_daily_collector_action_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_daily_collector_action_owner_due", "owner_user_id", "due_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    action_type: str = Field(max_length=16, nullable=False, index=True)
    priority_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    due_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    title: str = Field(max_length=512, nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    source_recommendation_id: int | None = Field(default=None, nullable=True, index=True)
    source_systems: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
