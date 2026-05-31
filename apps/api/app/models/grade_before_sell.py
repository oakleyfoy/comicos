from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


GRADE_BEFORE_SELL_RECOMMENDATIONS = ("GRADE_BEFORE_SELL", "SELL_RAW", "HOLD_FOR_REVIEW")


class GradeBeforeSellRecommendation(SQLModel, table=True):
    __tablename__ = "grade_before_sell_recommendation"
    __table_args__ = (
        SAIndex(
            "ix_grade_before_sell_owner_item",
            "owner_user_id",
            "inventory_item_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_grade_before_sell_owner_rec", "owner_user_id", "recommendation", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    recommendation: str = Field(max_length=24, nullable=False)
    current_estimated_value: float = Field(nullable=False)
    expected_graded_value: float = Field(nullable=False)
    estimated_grading_cost: float = Field(nullable=False)
    expected_value_gain: float = Field(nullable=False)
    expected_roi: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
