from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


EXIT_CANDIDATE_REASONS = (
    "DUPLICATE",
    "PROFITABLE",
    "GRADED",
    "OVEREXPOSED",
    "CAPITAL_RECOVERY",
    "MULTIPLE_SIGNALS",
)


class ExitCandidate(SQLModel, table=True):
    __tablename__ = "exit_candidate"
    __table_args__ = (
        SAIndex(
            "ix_exit_candidate_owner_item",
            "owner_user_id",
            "inventory_item_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_exit_candidate_owner_reason", "owner_user_id", "candidate_reason", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    candidate_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    estimated_fmv: float = Field(nullable=False)
    acquisition_cost: float = Field(nullable=False)
    unrealized_gain: float = Field(nullable=False)
    candidate_reason: str = Field(max_length=32, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
