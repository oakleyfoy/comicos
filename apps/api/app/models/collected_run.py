from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


COLLECTED_RUN_STATUSES = ("ACTIVE", "INACTIVE", "COMPLETE", "UNKNOWN")


class CollectedRun(SQLModel, table=True):
    __tablename__ = "collected_run"
    __table_args__ = (
        SAIndex("ix_collected_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_collected_run_publisher_series", "publisher", "series_name", "id"),
        SAIndex("ix_collected_run_owner_status", "owner_user_id", "run_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(max_length=120, nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    latest_owned_issue: str = Field(max_length=32, nullable=False)
    total_owned_issues: int = Field(nullable=False)
    run_status: str = Field(max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
