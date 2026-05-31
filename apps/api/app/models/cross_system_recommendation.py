from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


CROSS_SYSTEM_RECOMMENDATION_TYPES = (
    "PREORDER",
    "ACQUIRE",
    "GRADE",
    "SELL",
    "REBALANCE",
    "WATCH",
)


class CrossSystemRecommendation(SQLModel, table=True):
    __tablename__ = "cross_system_recommendation"
    __table_args__ = (
        SAIndex(
            "ix_cross_system_rec_owner_rank",
            "owner_user_id",
            "recommendation_rank",
            "created_at",
            "id",
        ),
        SAIndex("ix_cross_system_rec_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_type: str = Field(max_length=16, nullable=False, index=True)
    priority_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    title: str = Field(max_length=512, nullable=False)
    estimated_value: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    recommendation_rank: int = Field(nullable=False, index=True)
    source_systems: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
