from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_PUBLISHER_INCLUSION_STATUSES = ("INCLUDED", "EXCLUDED")


class IndustryPublisher(SQLModel, table=True):
    __tablename__ = "industry_publisher"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "publisher_code", name="uq_industry_publisher_owner_code"),
        SAIndex("ix_industry_publisher_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_industry_publisher_owner_inclusion", "owner_user_id", "inclusion_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher_code: str = Field(max_length=32, nullable=False, index=True)
    publisher_name: str = Field(max_length=120, nullable=False)
    scan_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    inclusion_status: str = Field(default="INCLUDED", max_length=16, nullable=False, index=True)
    scan_priority: int = Field(default=100, nullable=False)
    classification_mode: str = Field(default="STANDARD", max_length=32, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
