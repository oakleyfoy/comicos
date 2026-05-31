from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreatorProfile(SQLModel, table=True):
    __tablename__ = "creator_profile"
    __table_args__ = (UniqueConstraint("creator_name", "creator_role", name="uq_creator_profile_name_role"),)

    id: int | None = Field(default=None, primary_key=True)
    creator_name: str = Field(max_length=160, nullable=False, index=True)
    creator_role: str = Field(max_length=32, nullable=False, index=True)
    status: str = Field(default="ACTIVE", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CreatorPopularityScore(SQLModel, table=True):
    __tablename__ = "creator_popularity_score"
    __table_args__ = (
        SAIndex("ix_creator_popularity_creator_created", "creator_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    creator_id: int = Field(foreign_key="creator_profile.id", nullable=False, index=True)
    popularity_score: float = Field(nullable=False, index=True)
    demand_score: float = Field(nullable=False)
    collector_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    source_version: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CreatorAlias(SQLModel, table=True):
    __tablename__ = "creator_alias"
    __table_args__ = (
        UniqueConstraint("creator_id", "alias_name", name="uq_creator_alias"),
        SAIndex("ix_creator_alias_name", "alias_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    creator_id: int = Field(foreign_key="creator_profile.id", nullable=False, index=True)
    alias_name: str = Field(max_length=160, nullable=False, index=True)
