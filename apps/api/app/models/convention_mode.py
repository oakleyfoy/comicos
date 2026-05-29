from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConventionSession(SQLModel, table=True):
    __tablename__ = "convention_sessions"
    __table_args__ = (
        SAIndex("ix_convention_session_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_convention_session_org_status_created", "organization_id", "session_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    session_name: str = Field(max_length=200, nullable=False)
    session_status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionBooth(SQLModel, table=True):
    __tablename__ = "convention_booths"
    __table_args__ = (
        SAIndex("ix_convention_booth_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_convention_booth_session_created", "convention_session_id", "created_at", "id"),
        SAIndex("ix_convention_booth_org_status_created", "organization_id", "booth_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    convention_session_id: int = Field(foreign_key="convention_sessions.id", nullable=False, index=True)
    booth_name: str = Field(max_length=200, nullable=False)
    booth_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionInventoryStage(SQLModel, table=True):
    __tablename__ = "convention_inventory_stages"
    __table_args__ = (
        SAIndex("ix_convention_inv_stage_org_staged", "organization_id", "staged_at", "id"),
        SAIndex("ix_convention_inv_stage_session_staged", "convention_session_id", "staged_at", "id"),
        SAIndex("ix_convention_inv_stage_org_status_staged", "organization_id", "stage_status", "staged_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    convention_session_id: int = Field(foreign_key="convention_sessions.id", nullable=False, index=True)
    inventory_item_id: int = Field(nullable=False, index=True)
    stage_status: str = Field(max_length=24, nullable=False, index=True)
    staged_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionActivity(SQLModel, table=True):
    __tablename__ = "convention_activities"
    __table_args__ = (
        SAIndex("ix_convention_activity_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_convention_activity_session_created", "convention_session_id", "created_at", "id"),
        SAIndex("ix_convention_activity_org_type_created", "organization_id", "activity_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    convention_session_id: int = Field(foreign_key="convention_sessions.id", nullable=False, index=True)
    activity_type: str = Field(max_length=32, nullable=False, index=True)
    activity_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionModeEvent(SQLModel, table=True):
    __tablename__ = "convention_mode_events"
    __table_args__ = (
        SAIndex("ix_convention_mode_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_convention_mode_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_convention_mode_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
