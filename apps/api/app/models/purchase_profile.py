from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PURCHASE_PROFILE_TYPES = (
    "INVESTOR",
    "COLLECTOR",
    "READER",
    "VARIANT_HUNTER",
    "LONG_TERM_HOLD",
)

DEFAULT_PROFILE_TYPE = "COLLECTOR"


class PurchaseProfile(SQLModel, table=True):
    __tablename__ = "purchase_profile"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_purchase_profile_owner"),
        SAIndex("ix_purchase_profile_owner_active", "owner_user_id", "is_active", "id"),
        SAIndex("ix_purchase_profile_type", "profile_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    profile_type: str = Field(default=DEFAULT_PROFILE_TYPE, max_length=32, nullable=False)
    display_name: str = Field(default="", max_length=120, nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PurchasePreference(SQLModel, table=True):
    __tablename__ = "purchase_preference"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_purchase_preference_owner"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    preferred_copy_count: int = Field(default=1, nullable=False)
    risk_tolerance: float = Field(default=0.5, nullable=False)
    variant_interest: float = Field(default=0.5, nullable=False)
    grading_interest: float = Field(default=0.5, nullable=False)
    completionist_score: float = Field(default=0.5, nullable=False)
    speculation_score: float = Field(default=0.5, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
