from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


REBALANCE_TYPES = (
    "TITLE_OVEREXPOSURE",
    "PUBLISHER_OVEREXPOSURE",
    "CHARACTER_OVEREXPOSURE",
    "MODERN_SPEC_OVEREXPOSURE",
    "DUPLICATE_CAPITAL",
    "LOW_EFFICIENCY_CAPITAL",
)

REBALANCE_ACTIONS = ("REDUCE_EXPOSURE", "REVIEW_POSITION", "HOLD")

TITLE_EXPOSURE_THRESHOLD = 0.20
PUBLISHER_EXPOSURE_THRESHOLD = 0.40
MODERN_SPEC_YEAR = 2010
MODERN_SPEC_THRESHOLD = 0.25
CHARACTER_EXPOSURE_THRESHOLD = 0.22
DUPLICATE_MIN_COPIES = 3
DUPLICATE_MIN_FMV = 25.0


class PortfolioRebalanceRecommendation(SQLModel, table=True):
    __tablename__ = "portfolio_rebalance_recommendation"
    __table_args__ = (
        SAIndex(
            "ix_portfolio_rebalance_owner_type_key",
            "owner_user_id",
            "rebalance_type",
            "target_key",
            "created_at",
            "id",
        ),
        SAIndex("ix_portfolio_rebalance_owner_action", "owner_user_id", "recommended_action", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    rebalance_type: str = Field(max_length=32, nullable=False)
    target_key: str = Field(max_length=256, nullable=False)
    target_label: str = Field(max_length=512, nullable=False)
    exposure_value: float = Field(nullable=False)
    exposure_percent: float = Field(nullable=False)
    recommended_action: str = Field(max_length=24, nullable=False)
    priority_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
