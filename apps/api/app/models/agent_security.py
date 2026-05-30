from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentPermissionPolicy(SQLModel, table=True):
    __tablename__ = "agent_permission_policy"
    __table_args__ = (
        UniqueConstraint("agent_id", "capability_code", "permission_scope", name="uq_agent_permission_policy_edge"),
        SAIndex("ix_agent_permission_policy_agent_scope", "agent_id", "permission_scope", "id"),
        SAIndex("ix_agent_permission_policy_capability_scope", "capability_code", "permission_scope", "id"),
        SAIndex("ix_agent_permission_policy_allowed_updated", "allowed", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    capability_code: str = Field(max_length=120, nullable=False, index=True)
    permission_scope: str = Field(max_length=24, nullable=False, index=True)
    allowed: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentPermissionAuditEvent(SQLModel, table=True):
    __tablename__ = "agent_permission_audit_event"
    __table_args__ = (
        SAIndex("ix_agent_permission_audit_agent_created", "agent_id", "created_at", "id"),
        SAIndex("ix_agent_permission_audit_capability_created", "capability_code", "created_at", "id"),
        SAIndex("ix_agent_permission_audit_decision_created", "decision", "created_at", "id"),
        SAIndex("ix_agent_permission_audit_execution_created", "execution_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    execution_id: int | None = Field(default=None, foreign_key="agent_execution.id", nullable=True, index=True)
    capability_code: str = Field(max_length=120, nullable=False, index=True)
    action_code: str = Field(max_length=120, nullable=False, index=True)
    decision: str = Field(max_length=24, nullable=False, index=True)
    reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
