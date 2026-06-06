"""P72-03 grading outcome records for analytics and certification."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P72GradingOutcome(SQLModel, table=True):
    __tablename__ = "p72_grading_outcome"
    __table_args__ = (
        UniqueConstraint("queue_entry_id", name="uq_p72_grading_outcome_queue_entry"),
        SAIndex("ix_p72_grading_outcome_owner_recorded", "owner_user_id", "recorded_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    queue_entry_id: int = Field(foreign_key="p72_grading_queue_entry.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(max_length=256, nullable=False)
    publisher: str = Field(default="", max_length=80, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    series: str = Field(default="", max_length=160, nullable=False)
    era: str = Field(default="", max_length=32, nullable=False)
    recommendation: str = Field(max_length=32, nullable=False)
    pressing_recommended: str = Field(max_length=16, nullable=False)
    was_pressed: bool = Field(default=False, nullable=False)
    expected_grade: str = Field(max_length=16, nullable=False)
    actual_grade: str = Field(max_length=16, nullable=False)
    expected_roi_pct: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    actual_roi_pct: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    expected_profit: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    actual_profit: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    raw_fmv: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    graded_value_estimate: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    actual_grading_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    recommendation_accuracy: str = Field(max_length=16, nullable=False, index=True)
    queue_status: str = Field(max_length=32, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    recorded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
