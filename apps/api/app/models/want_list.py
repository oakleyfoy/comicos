from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_WANT_LIST_NAME = "My Want List"

WANT_LIST_PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
WANT_LIST_STATUSES = ("WANTED", "FOUND", "ACQUIRED", "REMOVED")

DEFAULT_PRIORITY = "MEDIUM"
DEFAULT_STATUS = "WANTED"


class WantList(SQLModel, table=True):
    __tablename__ = "want_list"
    __table_args__ = (
        SAIndex("ix_want_list_owner_active", "owner_user_id", "is_active", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    name: str = Field(max_length=120, nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class WantListItem(SQLModel, table=True):
    __tablename__ = "want_list_item"
    __table_args__ = (
        SAIndex("ix_want_list_item_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_want_list_item_owner_priority", "owner_user_id", "priority", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    want_list_id: int = Field(foreign_key="want_list.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(default="", max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False)
    issue_number: str = Field(max_length=32, nullable=False)
    variant_description: str = Field(default="", max_length=200, nullable=False)
    priority: str = Field(default=DEFAULT_PRIORITY, max_length=16, nullable=False, index=True)
    status: str = Field(default=DEFAULT_STATUS, max_length=16, nullable=False, index=True)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
