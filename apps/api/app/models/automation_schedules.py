from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationSchedule(SQLModel, table=True):
    __tablename__ = "automation_schedules"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "schedule_key", name="uq_automation_schedule_owner_key"),
        SAIndex("ix_automation_schedule_status_next", "schedule_status", "next_run_at", "id"),
        SAIndex("ix_automation_schedule_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    schedule_key: str = Field(max_length=120, nullable=False, index=True)
    schedule_name: str = Field(max_length=160, nullable=False)
    schedule_type: str = Field(max_length=24, nullable=False, index=True)
    schedule_status: str = Field(max_length=24, nullable=False, index=True)
    cron_expression: str | None = Field(default=None, max_length=120, nullable=True)
    interval_seconds: int | None = Field(default=None, nullable=True)
    next_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    deterministic_ordering_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    schedule_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationTrigger(SQLModel, table=True):
    __tablename__ = "automation_triggers"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "trigger_checksum", name="uq_automation_trigger_owner_checksum"),
        SAIndex("ix_automation_trigger_status_created", "trigger_status", "created_at", "id"),
        SAIndex("ix_automation_trigger_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    trigger_key: str = Field(max_length=120, nullable=False, index=True)
    trigger_type: str = Field(max_length=40, nullable=False, index=True)
    trigger_status: str = Field(max_length=24, nullable=False, index=True)
    source_event_type: str = Field(max_length=80, nullable=False, index=True)
    source_record_type: str | None = Field(default=None, max_length=80, nullable=True, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    source_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    trigger_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    trigger_checksum: str = Field(max_length=64, nullable=False, index=True)
    triggered_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkflow(SQLModel, table=True):
    __tablename__ = "automation_workflows"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "workflow_key", name="uq_automation_workflow_owner_key"),
        SAIndex("ix_automation_workflow_status_created", "workflow_status", "created_at", "id"),
        SAIndex("ix_automation_workflow_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    workflow_key: str = Field(max_length=120, nullable=False, index=True)
    workflow_name: str = Field(max_length=160, nullable=False)
    workflow_status: str = Field(max_length=24, nullable=False, index=True)
    workflow_category: str = Field(max_length=40, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    deterministic_ordering_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkflowStep(SQLModel, table=True):
    __tablename__ = "automation_workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_rank", name="uq_automation_workflow_step_rank"),
        UniqueConstraint("workflow_id", "step_key", name="uq_automation_workflow_step_key"),
        SAIndex("ix_automation_workflow_step_workflow_rank", "workflow_id", "step_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="automation_workflows.id", nullable=False, index=True)
    step_rank: int = Field(nullable=False, index=True)
    step_key: str = Field(max_length=120, nullable=False, index=True)
    job_type: str = Field(max_length=40, nullable=False, index=True)
    dependency_mode: str = Field(max_length=24, nullable=False, index=True)
    delay_seconds: int | None = Field(default=None, nullable=True)
    required_success: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkflowExecution(SQLModel, table=True):
    __tablename__ = "automation_workflow_executions"
    __table_args__ = (
        UniqueConstraint("execution_checksum", name="uq_automation_workflow_execution_checksum"),
        SAIndex("ix_automation_workflow_exec_workflow_created", "workflow_id", "created_at", "id"),
        SAIndex("ix_automation_workflow_exec_status_created", "execution_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="automation_workflows.id", nullable=False, index=True)
    trigger_id: int | None = Field(default=None, foreign_key="automation_triggers.id", nullable=True, index=True)
    schedule_id: int | None = Field(default=None, foreign_key="automation_schedules.id", nullable=True, index=True)
    execution_status: str = Field(max_length=24, nullable=False, index=True)
    execution_checksum: str = Field(max_length=64, nullable=False, index=True)
    execution_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkflowIssue(SQLModel, table=True):
    __tablename__ = "automation_workflow_issues"
    __table_args__ = (
        UniqueConstraint("workflow_id", "issue_checksum", name="uq_automation_workflow_issue_checksum"),
        SAIndex("ix_automation_workflow_issue_workflow_created", "workflow_id", "created_at", "id"),
        SAIndex("ix_automation_workflow_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="automation_workflows.id", nullable=False, index=True)
    execution_id: int | None = Field(default=None, foreign_key="automation_workflow_executions.id", nullable=True, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkflowHistory(SQLModel, table=True):
    __tablename__ = "automation_workflow_history"
    __table_args__ = (
        UniqueConstraint("workflow_id", "event_checksum", name="uq_automation_workflow_history_checksum"),
        SAIndex("ix_automation_workflow_history_workflow_created", "workflow_id", "created_at", "id"),
        SAIndex("ix_automation_workflow_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="automation_workflows.id", nullable=False, index=True)
    execution_id: int | None = Field(default=None, foreign_key="automation_workflow_executions.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
