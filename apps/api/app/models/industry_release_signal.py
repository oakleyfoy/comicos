from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_RELEASE_SIGNAL_TYPES = (
    "NUMBER_ONE",
    "FIRST_APPEARANCE",
    "RATIO_VARIANT",
    "FACSIMILE",
    "ANNIVERSARY",
    "KEY_EVENT",
    "NEW_SERIES",
    "ONE_SHOT",
    "CROSSOVER",
    "MILESTONE",
    "UNKNOWN",
)


class IndustryReleaseSignal(SQLModel, table=True):
    __tablename__ = "industry_release_signal"
    __table_args__ = (
        UniqueConstraint("candidate_id", "signal_type", name="uq_industry_release_signal_candidate_type"),
        SAIndex("ix_industry_release_signal_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_industry_release_signal_owner_type", "owner_user_id", "signal_type", "id"),
        SAIndex("ix_industry_release_signal_scan_run", "scan_run_id", "signal_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    candidate_id: int = Field(foreign_key="industry_release_candidate.id", nullable=False, index=True)
    scan_run_id: int = Field(foreign_key="industry_release_scan_run.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    signal_type: str = Field(max_length=32, nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
