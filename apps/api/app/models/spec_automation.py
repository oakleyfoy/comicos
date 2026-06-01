from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SPEC_AUTOMATION_STATUSES = ("SUCCESS", "FAILED", "NO_CHANGE", "PARTIAL")


class SpecAutomationRun(SQLModel, table=True):
    __tablename__ = "spec_automation_run"
    __table_args__ = (
        SAIndex("ix_spec_automation_run_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_spec_automation_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="SUCCESS", max_length=16, nullable=False, index=True)
    inputs_processed: int = Field(default=0, nullable=False)
    baseline_scores_created: int = Field(default=0, nullable=False)
    ai_evaluations_created: int = Field(default=0, nullable=False)
    top_picks_created: int = Field(default=0, nullable=False)
    runtime_ms: int = Field(default=0, nullable=False)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
