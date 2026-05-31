from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserPreferenceProfile(SQLModel, table=True):
    __tablename__ = "user_preference_profile"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "preference_type", "preference_key", name="uq_user_preference_profile"),
        SAIndex("ix_user_preference_profile_owner", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    preference_type: str = Field(max_length=32, nullable=False, index=True)
    preference_key: str = Field(max_length=160, nullable=False, index=True)
    preference_label: str = Field(max_length=160, nullable=False)
    status: str = Field(default="ACTIVE", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class UserPreferenceSignal(SQLModel, table=True):
    __tablename__ = "user_preference_signal"
    __table_args__ = (SAIndex("ix_user_preference_signal_owner", "owner_user_id", "source_type", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    preference_profile_id: int = Field(foreign_key="user_preference_profile.id", nullable=False, index=True)
    signal_type: str = Field(max_length=48, nullable=False, index=True)
    signal_strength: float = Field(default=0.0, nullable=False)
    source_type: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class UserPreferenceScore(SQLModel, table=True):
    __tablename__ = "user_preference_score"
    __table_args__ = (SAIndex("ix_user_preference_score_profile", "preference_profile_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    preference_profile_id: int = Field(foreign_key="user_preference_profile.id", nullable=False, index=True)
    preference_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
