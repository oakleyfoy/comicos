from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PurchaseQuantityRecommendation(SQLModel, table=True):
    __tablename__ = "purchase_quantity_recommendation"
    __table_args__ = (
        SAIndex("ix_purchase_qty_rec_owner_release", "owner_user_id", "release_id", "created_at", "id"),
        SAIndex("ix_purchase_qty_rec_owner_tier", "owner_user_id", "recommendation_tier", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    recommendation_tier: str = Field(max_length=24, nullable=False)
    quantity_recommended: int = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
