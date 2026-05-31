from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SELL_CANDIDATE_RECOMMENDATIONS = ("STRONG_SELL", "SELL", "HOLD", "REVIEW")

KEEP_COPIES_DEFAULT = 2


class SellCandidateRecommendation(SQLModel, table=True):
    __tablename__ = "sell_candidate_recommendation"
    __table_args__ = (
        SAIndex(
            "ix_sell_candidate_rec_owner_item",
            "owner_user_id",
            "inventory_item_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_sell_candidate_rec_owner_rec", "owner_user_id", "recommendation", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    recommendation: str = Field(max_length=16, nullable=False)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    estimated_fmv: float = Field(nullable=False)
    estimated_profit: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
