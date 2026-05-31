from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PurchaseBudget(SQLModel, table=True):
    __tablename__ = "purchase_budget"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_purchase_budget_owner"),
        SAIndex("ix_purchase_budget_owner_active", "owner_user_id", "is_active", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    monthly_budget: float = Field(default=0.0, nullable=False)
    weekly_budget: float = Field(default=0.0, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PurchaseBudgetAllocation(SQLModel, table=True):
    __tablename__ = "purchase_budget_allocation"
    __table_args__ = (
        SAIndex(
            "ix_purchase_budget_alloc_owner_release",
            "owner_user_id",
            "release_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_purchase_budget_alloc_owner_tier", "owner_user_id", "recommendation_tier", "id"),
        SAIndex("ix_purchase_budget_alloc_owner_rank", "owner_user_id", "priority_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    recommendation_tier: str = Field(max_length=24, nullable=False)
    allocated_amount: float = Field(nullable=False)
    priority_rank: int = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
