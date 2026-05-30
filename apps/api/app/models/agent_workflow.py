from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowDefinition(SQLModel, table=True):
    __tablename__ = "workflow_definition"
    __table_args__ = (
        UniqueConstraint("workflow_code", name="uq_workflow_definition_code"),
        SAIndex("ix_workflow_definition_created", "created_at", "id"),
        SAIndex("ix_workflow_definition_enabled_created", "enabled", "created_at", "id"),
        SAIndex("ix_workflow_definition_schedule_next", "schedule_enabled", "next_run_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_code: str = Field(max_length=80, nullable=False, index=True)
    workflow_name: str = Field(max_length=160, nullable=False)
    description: str = Field(max_length=1000, nullable=False)
    enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    schedule_enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    cron_expression: str | None = Field(default=None, max_length=120, nullable=True)
    next_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class WorkflowStep(SQLModel, table=True):
    __tablename__ = "workflow_step"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_workflow_step_order"),
        UniqueConstraint("workflow_id", "step_code", name="uq_workflow_step_code"),
        SAIndex("ix_workflow_step_workflow_order", "workflow_id", "step_order", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow_definition.id", nullable=False, index=True)
    step_order: int = Field(nullable=False, index=True)
    agent_definition_id: int = Field(foreign_key="agent_definition.id", nullable=False, index=True)
    step_name: str = Field(max_length=160, nullable=False)
    step_code: str = Field(max_length=80, nullable=False, index=True)
    required_success: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    timeout_seconds: int | None = Field(default=None, nullable=True)


class WorkflowExecution(SQLModel, table=True):
    __tablename__ = "workflow_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_workflow_execution_uuid"),
        SAIndex("ix_workflow_execution_workflow_started", "workflow_id", "started_at", "id"),
        SAIndex("ix_workflow_execution_status_started", "status", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow_definition.id", nullable=False, index=True)
    execution_uuid: str = Field(max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    triggered_by: str = Field(max_length=255, nullable=False)
    trigger_source: str = Field(max_length=80, nullable=False)


class WorkflowStepExecution(SQLModel, table=True):
    __tablename__ = "workflow_step_execution"
    __table_args__ = (
        UniqueConstraint("workflow_execution_id", "workflow_step_id", name="uq_workflow_step_execution_edge"),
        UniqueConstraint("agent_execution_id", name="uq_workflow_step_execution_agent_execution"),
        SAIndex("ix_workflow_step_execution_workflow_started", "workflow_execution_id", "started_at", "id"),
        SAIndex("ix_workflow_step_execution_status_started", "status", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_execution_id: int = Field(foreign_key="workflow_execution.id", nullable=False, index=True)
    workflow_step_id: int = Field(foreign_key="workflow_step.id", nullable=False, index=True)
    agent_execution_id: int = Field(foreign_key="agent_execution.id", nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
