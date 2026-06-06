"""P77-01 collector profile, interests, goals, and budget."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P77CollectorProfile(SQLModel, table=True):
    __tablename__ = "p77_collector_profile"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_p77_collector_profile_owner"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    collector_type: str = Field(default="HYBRID", max_length=32, nullable=False)
    risk_profile: str = Field(default="MODERATE", max_length=32, nullable=False)
    time_horizon: str = Field(default="LONG_TERM", max_length=32, nullable=False)
    grading_preference: str = Field(default="OPPORTUNISTIC", max_length=32, nullable=False)
    hold_preference: str = Field(default="MIXED", max_length=32, nullable=False)
    default_copy_count: int = Field(default=2, nullable=False)
    key_issue_copy_count: int = Field(default=4, nullable=False)
    ratio_variant_copy_count: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P77CollectorInterest(SQLModel, table=True):
    __tablename__ = "p77_collector_interest"
    __table_args__ = (
        SAIndex("ix_p77_interest_owner_type_rank", "owner_user_id", "interest_type", "priority_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    interest_type: str = Field(max_length=16, nullable=False, index=True)
    label: str = Field(max_length=120, nullable=False)
    priority_rank: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P77CollectorGoal(SQLModel, table=True):
    __tablename__ = "p77_collector_goal"
    __table_args__ = (SAIndex("ix_p77_goal_owner_type", "owner_user_id", "goal_type", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    goal_type: str = Field(max_length=32, nullable=False, index=True)
    title: str = Field(max_length=200, nullable=False)
    target_value: float = Field(default=0.0, nullable=False)
    progress_value: float = Field(default=0.0, nullable=False)
    completion_percent: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P77CollectorBudget(SQLModel, table=True):
    __tablename__ = "p77_collector_budget"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_p77_collector_budget_owner"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    monthly_budget: float = Field(default=0.0, nullable=False)
    budget_period: str = Field(default="MONTHLY", max_length=16, nullable=False)
    publisher_allocations_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    category_allocations_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
