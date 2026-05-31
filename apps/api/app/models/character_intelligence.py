from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CharacterProfile(SQLModel, table=True):
    __tablename__ = "character_profile"
    __table_args__ = (
        UniqueConstraint("character_name", "publisher", name="uq_character_profile_name_publisher"),
        SAIndex("ix_character_profile_publisher_name", "publisher", "character_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character_name: str = Field(max_length=160, nullable=False)
    publisher: str = Field(max_length=120, nullable=False)
    franchise_id: int | None = Field(default=None, foreign_key="franchise_profile.id", nullable=True, index=True)
    status: str = Field(default="ACTIVE", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CharacterPopularityScore(SQLModel, table=True):
    __tablename__ = "character_popularity_score"
    __table_args__ = (
        SAIndex("ix_character_popularity_character_created", "character_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character_profile.id", nullable=False, index=True)
    popularity_score: float = Field(nullable=False, index=True)
    demand_score: float = Field(nullable=False)
    collector_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    source_version: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CharacterAlias(SQLModel, table=True):
    __tablename__ = "character_alias"
    __table_args__ = (
        UniqueConstraint("character_id", "alias_name", name="uq_character_alias"),
        SAIndex("ix_character_alias_name", "alias_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character_profile.id", nullable=False, index=True)
    alias_name: str = Field(max_length=160, nullable=False, index=True)


class CharacterAppearance(SQLModel, table=True):
    __tablename__ = "character_appearance"
    __table_args__ = (
        SAIndex("ix_character_appearance_issue", "release_issue_id", "appearance_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="character_profile.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    appearance_type: str = Field(max_length=32, nullable=False, index=True)
