from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationRetryPolicy(SQLModel, table=True):
    __tablename__ = "automation_retry_policies"
    __table_args__ = (
        UniqueConstraint("policy_key", name="uq_automation_retry_policy_key"),
        SAIndex("ix_automation_retry_policy_mode_created", "retry_mode", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    policy_key: str = Field(max_length=120, nullable=False, index=True)
    policy_name: str = Field(max_length=160, nullable=False)
    retry_mode: str = Field(max_length=32, nullable=False, index=True)
    max_attempts: int = Field(nullable=False)
    base_delay_seconds: int = Field(nullable=False)
    max_delay_seconds: int = Field(nullable=False)
    deterministic_backoff_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    dead_letter_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    policy_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRecoveryRun(SQLModel, table=True):
    __tablename__ = "automation_recovery_runs"
    __table_args__ = (
        UniqueConstraint("recovery_checksum", name="uq_automation_recovery_run_checksum"),
        SAIndex("ix_automation_recovery_run_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_recovery_run_status_created", "recovery_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    worker_execution_id: int | None = Field(default=None, foreign_key="automation_worker_executions.id", nullable=True, index=True)
    retry_policy_id: int | None = Field(default=None, foreign_key="automation_retry_policies.id", nullable=True, index=True)
    recovery_status: str = Field(max_length=24, nullable=False, index=True)
    recovery_type: str = Field(max_length=32, nullable=False, index=True)
    recovery_rank: int = Field(nullable=False, index=True)
    recovery_checksum: str = Field(max_length=64, nullable=False, index=True)
    recovery_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationDeadLetterJob(SQLModel, table=True):
    __tablename__ = "automation_dead_letter_jobs"
    __table_args__ = (
        UniqueConstraint("original_job_id", name="uq_automation_dead_letter_original_job"),
        SAIndex("ix_automation_dead_letter_status_created", "dead_letter_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    original_job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    dead_letter_reason: str = Field(max_length=1024, nullable=False)
    dead_letter_status: str = Field(max_length=24, nullable=False, index=True)
    failure_count: int = Field(nullable=False)
    source_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    dead_letter_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationFailureEvent(SQLModel, table=True):
    __tablename__ = "automation_failure_events"
    __table_args__ = (
        UniqueConstraint("failure_checksum", name="uq_automation_failure_event_checksum"),
        SAIndex("ix_automation_failure_event_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_failure_event_severity_created", "failure_severity", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int | None = Field(default=None, foreign_key="automation_jobs.id", nullable=True, index=True)
    worker_execution_id: int | None = Field(default=None, foreign_key="automation_worker_executions.id", nullable=True, index=True)
    failure_type: str = Field(max_length=64, nullable=False, index=True)
    failure_severity: str = Field(max_length=16, nullable=False, index=True)
    failure_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    failure_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRecoveryArtifact(SQLModel, table=True):
    __tablename__ = "automation_recovery_artifacts"
    __table_args__ = (
        UniqueConstraint("recovery_run_id", "artifact_type", "artifact_checksum", name="uq_automation_recovery_artifact_type_checksum"),
        SAIndex("ix_automation_recovery_artifact_run_created", "recovery_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recovery_run_id: int = Field(foreign_key="automation_recovery_runs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRecoveryIssue(SQLModel, table=True):
    __tablename__ = "automation_recovery_issues"
    __table_args__ = (
        UniqueConstraint("recovery_run_id", "issue_checksum", name="uq_automation_recovery_issue_checksum"),
        SAIndex("ix_automation_recovery_issue_run_created", "recovery_run_id", "created_at", "id"),
        SAIndex("ix_automation_recovery_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recovery_run_id: int = Field(foreign_key="automation_recovery_runs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationRecoveryHistory(SQLModel, table=True):
    __tablename__ = "automation_recovery_history"
    __table_args__ = (
        UniqueConstraint("recovery_run_id", "event_checksum", name="uq_automation_recovery_history_checksum"),
        SAIndex("ix_automation_recovery_history_run_created", "recovery_run_id", "created_at", "id"),
        SAIndex("ix_automation_recovery_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recovery_run_id: int = Field(foreign_key="automation_recovery_runs.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
