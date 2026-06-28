"""P108 — user data collections (real + disposable test clones)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


COLLECTION_TYPE_REAL = "real"
COLLECTION_TYPE_TEST = "test"
COLLECTION_TYPE_SANDBOX = "sandbox"
COLLECTION_TYPES = (COLLECTION_TYPE_REAL, COLLECTION_TYPE_TEST, COLLECTION_TYPE_SANDBOX)

DEFAULT_REAL_COLLECTION_NAME = "Oakley Real Collection"


class UserDataCollection(SQLModel, table=True):
    __tablename__ = "user_data_collection"
    __table_args__ = (
        SAIndex("ix_user_data_collection_owner_active", "owner_user_id", "deleted_at", "id"),
        SAIndex("ix_user_data_collection_owner_type", "owner_user_id", "collection_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False)
    collection_type: str = Field(max_length=16, nullable=False, index=True)
    is_default: bool = Field(default=False, nullable=False)
    source_collection_id: int | None = Field(
        default=None,
        foreign_key="user_data_collection.id",
        nullable=True,
        index=True,
    )
    source_snapshot_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
