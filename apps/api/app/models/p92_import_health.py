"""P92-05 import health metrics events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P92ImportHealthEvent(SQLModel, table=True):
    __tablename__ = "p92_import_health_event"
    __table_args__ = (SAIndex("ix_p92_import_health_owner_created", "owner_user_id", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    draft_import_id: int | None = Field(default=None, foreign_key="draft_import.id", nullable=True, index=True)
    event_type: str = Field(max_length=48, nullable=False, index=True)
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
