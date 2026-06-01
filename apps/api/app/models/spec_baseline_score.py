from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpecBaselineScore(SQLModel, table=True):
    __tablename__ = "spec_baseline_score"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "spec_input_id", name="uq_spec_baseline_score_owner_input"),
        SAIndex("ix_spec_baseline_owner_score", "owner_user_id", "baseline_score", "id"),
        SAIndex("ix_spec_baseline_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spec_input_id: int = Field(foreign_key="spec_input.id", nullable=False, index=True)
    baseline_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    risk_score: float = Field(default=0.0, nullable=False, index=True)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
