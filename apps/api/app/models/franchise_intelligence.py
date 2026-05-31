from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FranchiseProfile(SQLModel, table=True):
    __tablename__ = "franchise_profile"
    __table_args__ = (UniqueConstraint("franchise_name", name="uq_franchise_profile_name"),)

    id: int | None = Field(default=None, primary_key=True)
    franchise_name: str = Field(max_length=160, nullable=False, index=True)
    primary_publisher: str = Field(max_length=120, nullable=False, index=True)
    status: str = Field(default="ACTIVE", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class FranchisePopularityScore(SQLModel, table=True):
    __tablename__ = "franchise_popularity_score"
    __table_args__ = (
        SAIndex("ix_franchise_popularity_franchise_created", "franchise_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    franchise_id: int = Field(foreign_key="franchise_profile.id", nullable=False, index=True)
    popularity_score: float = Field(nullable=False, index=True)
    demand_score: float = Field(nullable=False)
    longevity_score: float = Field(nullable=False)
    collector_strength_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    source_version: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
