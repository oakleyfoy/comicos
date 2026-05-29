from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationEvent(SQLModel, table=True):
    __tablename__ = "organization_events"
    __table_args__ = (
        SAIndex("ix_organization_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_organization_event_actor_created", "actor_user_id", "created_at", "id"),
        SAIndex("ix_organization_event_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
