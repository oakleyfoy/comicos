from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationQueue(SQLModel, table=True):
    __tablename__ = "automation_queues"
    __table_args__ = (
        UniqueConstraint("queue_key", name="uq_automation_queue_key"),
        SAIndex("ix_automation_queue_status_created", "queue_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    queue_key: str = Field(max_length=80, nullable=False, index=True)
    queue_name: str = Field(max_length=160, nullable=False)
    queue_category: str = Field(max_length=32, nullable=False, index=True)
    queue_status: str = Field(max_length=24, nullable=False, index=True)
    deterministic_ordering_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    max_concurrency: int = Field(default=1, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJob(SQLModel, table=True):
    __tablename__ = "automation_jobs"
    __table_args__ = (
        UniqueConstraint("queue_id", "job_key", name="uq_automation_job_queue_key"),
        SAIndex("ix_automation_job_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_automation_job_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_automation_job_queue_status_rank", "queue_id", "job_status", "deterministic_rank", "id"),
        SAIndex("ix_automation_job_queue_available", "queue_id", "available_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    queue_id: int = Field(foreign_key="automation_queues.id", nullable=False, index=True)
    parent_job_id: int | None = Field(default=None, foreign_key="automation_jobs.id", nullable=True, index=True)
    job_key: str = Field(max_length=160, nullable=False, index=True)
    job_type: str = Field(max_length=40, nullable=False, index=True)
    job_status: str = Field(max_length=24, nullable=False, index=True)
    priority: str = Field(max_length=16, nullable=False, index=True)
    deterministic_rank: int = Field(nullable=False, index=True)
    payload_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    payload_checksum: str = Field(max_length=64, nullable=False, index=True)
    source_record_type: str | None = Field(default=None, max_length=80, nullable=True, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    source_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    reservation_token: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    reserved_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    available_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    failed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    max_attempts: int = Field(default=1, nullable=False)
    current_attempt_count: int = Field(default=0, nullable=False)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    idempotency_key: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    job_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJobAttempt(SQLModel, table=True):
    __tablename__ = "automation_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_automation_job_attempt_job_number"),
        SAIndex("ix_automation_job_attempt_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_job_attempt_status_created", "attempt_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    attempt_number: int = Field(nullable=False)
    attempt_status: str = Field(max_length=16, nullable=False, index=True)
    worker_identifier: str | None = Field(default=None, max_length=160, nullable=True, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    failure_reason: str | None = Field(default=None, max_length=1024, nullable=True)
    execution_time_ms: int | None = Field(default=None, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJobDependency(SQLModel, table=True):
    __tablename__ = "automation_job_dependencies"
    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id", name="uq_automation_job_dependency_edge"),
        SAIndex("ix_automation_job_dependency_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_job_dependency_dep_created", "depends_on_job_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    depends_on_job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    dependency_status: str = Field(max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJobArtifact(SQLModel, table=True):
    __tablename__ = "automation_job_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "artifact_type", "artifact_checksum", name="uq_automation_job_artifact_type_checksum"),
        SAIndex("ix_automation_job_artifact_job_created", "job_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJobIssue(SQLModel, table=True):
    __tablename__ = "automation_job_issues"
    __table_args__ = (
        UniqueConstraint("job_id", "issue_checksum", name="uq_automation_job_issue_checksum"),
        SAIndex("ix_automation_job_issue_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_job_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationJobHistory(SQLModel, table=True):
    __tablename__ = "automation_job_history"
    __table_args__ = (
        UniqueConstraint("job_id", "event_checksum", name="uq_automation_job_history_checksum"),
        SAIndex("ix_automation_job_history_job_created", "job_id", "created_at", "id"),
        SAIndex("ix_automation_job_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="automation_jobs.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
