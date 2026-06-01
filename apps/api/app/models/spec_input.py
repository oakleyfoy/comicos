from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SPEC_INPUT_SOURCE_SYSTEMS = (
    "RELEASE_INTELLIGENCE",
    "FUTURE_RELEASE_INTELLIGENCE",
    "INDUSTRY_SCANNER",
    "PURCHASE_PROFILE",
    "PULL_LIST",
)


class SpecInput(SQLModel, table=True):
    __tablename__ = "spec_input"
    __table_args__ = (
        SAIndex("ix_spec_input_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_spec_input_owner_release", "owner_user_id", "release_id", "id"),
        SAIndex("ix_spec_input_owner_foc", "owner_user_id", "foc_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    industry_candidate_id: int | None = Field(
        default=None, foreign_key="industry_release_candidate.id", nullable=True, index=True
    )
    future_release_match_id: int | None = Field(default=None, foreign_key="future_release_match.id", nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False, index=True)
    series_name: str = Field(default="", max_length=200, nullable=False, index=True)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    source_systems: str = Field(default="", max_length=512, nullable=False)
    signal_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
