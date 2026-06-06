"""P73-01 persistent recommendation outcome tracking (feedback loop; no score changes)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationOutcome(SQLModel, table=True):
    __tablename__ = "p73_recommendation_outcome"
    __table_args__ = (
        SAIndex("ix_p73_rec_outcome_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_p73_rec_outcome_rec_id", "owner_user_id", "recommendation_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_id: str = Field(max_length=128, nullable=False, index=True)
    inventory_copy_id: int | None = Field(
        default=None,
        foreign_key="inventory_copy.id",
        nullable=True,
        index=True,
    )
    series: str = Field(default="", max_length=256, nullable=False)
    issue: str = Field(default="", max_length=32, nullable=False)
    variant: str = Field(default="", max_length=128, nullable=False)
    publisher: str = Field(default="", max_length=128, nullable=False)
    character: str = Field(default="", max_length=128, nullable=False)
    creator: str = Field(default="", max_length=128, nullable=False)
    recommendation_type: str = Field(max_length=32, nullable=False, index=True)
    recommendation_category: str = Field(max_length=32, nullable=False, index=True)
    created_date: date = Field(sa_column=Column(Date, nullable=False))
    current_status: str = Field(default="RECOMMENDED", max_length=32, nullable=False, index=True)
    attribution_outcome: str | None = Field(default=None, max_length=32, nullable=True)
    attribution_accurate: bool | None = Field(default=None, nullable=True)
    expected_profit: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    actual_profit: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    expected_roi_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_roi_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    source_table: str | None = Field(default=None, max_length=64, nullable=True)
    source_row_id: int | None = Field(default=None, nullable=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
