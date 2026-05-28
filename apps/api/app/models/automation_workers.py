from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationWorker(SQLModel, table=True):
    __tablename__ = "automation_workers"
    __table_args__ = (
        UniqueConstraint("worker_key", name="uq_automation_worker_key"),
        UniqueConstraint("worker_identifier", name="uq_automation_worker_identifier"),
        SAIndex("ix_automation_worker_status_created", "worker_status", "created_at", "id"),
        SAIndex("ix_automation_worker_type_created", "worker_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_key: str = Field(max_length=80, nullable=False, index=True)
    worker_identifier: str = Field(max_length=160, nullable=False, index=True)
    worker_type: str = Field(max_length=32, nullable=False, index=True)
    worker_status: str = Field(max_length=24, nullable=False, index=True)
    process_identifier: str | None = Field(default=None, max_length=80, nullable=True)
    hostname: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    queue_scope_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    current_job_id: int | None = Field(default=None, foreign_key="automation_jobs.id", nullable=True, index=True)
    max_concurrency: int = Field(default=1, nullable=False)
    last_heartbeat_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    startup_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    shutdown_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkerHeartbeat(SQLModel, table=True):
    __tablename__ = "automation_worker_heartbeats"
    __table_args__ = (
        SAIndex("ix_automation_worker_heartbeat_worker_created", "worker_id", "created_at", "id"),
        SAIndex("ix_automation_worker_heartbeat_status_created", "heartbeat_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="automation_workers.id", nullable=False, index=True)
    heartbeat_status: str = Field(max_length=16, nullable=False, index=True)
    active_job_count: int = Field(default=0, nullable=False)
    memory_usage_mb: int | None = Field(default=None, nullable=True)
    cpu_usage_percent: float | None = Field(default=None, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkerLease(SQLModel, table=True):
    __tablename__ = "automation_worker_leases"
    __table_args__ = (
        UniqueConstraint("reservation_token", name="uq_automation_worker_lease_token"),
        SAIndex("ix_automation_worker_lease_worker_created", "worker_id", "created_at", "id"),
        SAIndex("ix_automation_worker_lease_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_worker_lease_status_expires", "lease_status", "lease_expires_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="automation_workers.id", nullable=False, index=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    reservation_token: str = Field(max_length=128, nullable=False, index=True)
    lease_status: str = Field(max_length=16, nullable=False, index=True)
    lease_expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    acquired_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    released_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkerExecution(SQLModel, table=True):
    __tablename__ = "automation_worker_executions"
    __table_args__ = (
        UniqueConstraint("worker_id", "job_id", "execution_rank", name="uq_automation_worker_exec_worker_job_rank"),
        UniqueConstraint("execution_checksum", name="uq_automation_worker_exec_checksum"),
        SAIndex("ix_automation_worker_exec_worker_created", "worker_id", "created_at", "id"),
        SAIndex("ix_automation_worker_exec_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_worker_exec_status_created", "execution_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="automation_workers.id", nullable=False, index=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    execution_status: str = Field(max_length=16, nullable=False, index=True)
    execution_rank: int = Field(nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    execution_time_ms: int | None = Field(default=None, nullable=True)
    execution_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    execution_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkerIssue(SQLModel, table=True):
    __tablename__ = "automation_worker_issues"
    __table_args__ = (
        UniqueConstraint("worker_id", "issue_checksum", name="uq_automation_worker_issue_checksum"),
        SAIndex("ix_automation_worker_issue_worker_created", "worker_id", "created_at", "id"),
        SAIndex("ix_automation_worker_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="automation_workers.id", nullable=False, index=True)
    job_id: int | None = Field(default=None, foreign_key="automation_jobs.id", nullable=True, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationWorkerHistory(SQLModel, table=True):
    __tablename__ = "automation_worker_history"
    __table_args__ = (
        UniqueConstraint("worker_id", "event_checksum", name="uq_automation_worker_history_checksum"),
        SAIndex("ix_automation_worker_history_worker_created", "worker_id", "created_at", "id"),
        SAIndex("ix_automation_worker_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="automation_workers.id", nullable=False, index=True)
    job_id: int | None = Field(default=None, foreign_key="automation_jobs.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
