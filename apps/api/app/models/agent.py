from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentDefinition(SQLModel, table=True):
    __tablename__ = "agent_definition"
    __table_args__ = (
        UniqueConstraint("code", name="uq_agent_definition_code"),
        SAIndex("ix_agent_definition_created", "created_at", "id"),
        SAIndex("ix_agent_definition_enabled_created", "enabled", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=80, nullable=False, index=True)
    name: str = Field(max_length=160, nullable=False)
    description: str = Field(max_length=1000, nullable=False)
    version: str = Field(max_length=40, nullable=False)
    enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentCapability(SQLModel, table=True):
    __tablename__ = "agent_capability"
    __table_args__ = (
        UniqueConstraint("agent_id", "capability_code", name="uq_agent_capability_agent_code"),
        SAIndex("ix_agent_capability_agent_code", "agent_id", "capability_code", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    capability_code: str = Field(max_length=80, nullable=False, index=True)
    capability_name: str = Field(max_length=160, nullable=False)


class AgentExecution(SQLModel, table=True):
    __tablename__ = "agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_agent_execution_uuid"),
        SAIndex("ix_agent_execution_agent_started", "agent_id", "started_at", "id"),
        SAIndex("ix_agent_execution_status_started", "status", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    execution_uuid: str = Field(max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    execution_duration_ms: int | None = Field(default=None, nullable=True)
    triggered_by: str = Field(max_length=255, nullable=False)
    trigger_source: str = Field(max_length=80, nullable=False)


class AgentExecutionEvent(SQLModel, table=True):
    __tablename__ = "agent_execution_event"
    __table_args__ = (
        SAIndex("ix_agent_execution_event_execution_timestamp", "execution_id", "event_timestamp", "id"),
        SAIndex("ix_agent_execution_event_type_timestamp", "event_type", "event_timestamp", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    execution_id: int = Field(foreign_key="agent_execution.id", nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_timestamp: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
