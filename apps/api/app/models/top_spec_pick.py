from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TopSpecPick(SQLModel, table=True):
    __tablename__ = "top_spec_pick"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "rank", name="uq_top_spec_pick_owner_rank"),
        UniqueConstraint("owner_user_id", "spec_input_id", name="uq_top_spec_pick_owner_spec_input"),
        SAIndex("ix_top_spec_pick_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_top_spec_pick_owner_score", "owner_user_id", "final_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    rank: int = Field(nullable=False, index=True)
    release_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    spec_input_id: int = Field(foreign_key="spec_input.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False, index=True)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    final_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    risk_level: str = Field(default="MEDIUM", max_length=16, nullable=False, index=True)
    suggested_quantity: int | None = Field(default=None, nullable=True)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
