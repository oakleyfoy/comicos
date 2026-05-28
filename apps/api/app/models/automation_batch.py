from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationBatchRun(SQLModel, table=True):
    __tablename__ = "automation_batch_runs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "batch_key", name="uq_automation_batch_owner_key"),
        SAIndex("ix_automation_batch_run_status_created", "batch_status", "created_at", "id"),
        SAIndex("ix_automation_batch_run_type_created", "batch_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    batch_key: str = Field(max_length=120, nullable=False, index=True)
    batch_type: str = Field(max_length=40, nullable=False, index=True)
    batch_status: str = Field(max_length=24, nullable=False, index=True)
    source_scope: str = Field(max_length=80, nullable=False, index=True)
    deterministic_partitioning_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    total_item_count: int = Field(default=0, nullable=False)
    completed_item_count: int = Field(default=0, nullable=False)
    failed_item_count: int = Field(default=0, nullable=False)
    batch_checksum: str = Field(max_length=64, nullable=False, index=True)
    manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationBatchChunk(SQLModel, table=True):
    __tablename__ = "automation_batch_chunks"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "chunk_rank", name="uq_automation_batch_chunk_rank"),
        SAIndex("ix_automation_batch_chunk_run_created", "batch_run_id", "created_at", "id"),
        SAIndex("ix_automation_batch_chunk_status_created", "chunk_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_run_id: int = Field(foreign_key="automation_batch_runs.id", nullable=False, index=True)
    chunk_rank: int = Field(nullable=False, index=True)
    chunk_status: str = Field(max_length=24, nullable=False, index=True)
    partition_key: str = Field(max_length=120, nullable=False, index=True)
    item_start: int = Field(nullable=False)
    item_end: int = Field(nullable=False)
    item_count: int = Field(nullable=False)
    chunk_checksum: str = Field(max_length=64, nullable=False, index=True)
    worker_execution_id: int | None = Field(default=None, foreign_key="automation_worker_executions.id", nullable=True, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationMaintenanceJob(SQLModel, table=True):
    __tablename__ = "automation_maintenance_jobs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "maintenance_key", name="uq_automation_maintenance_owner_key"),
        SAIndex("ix_automation_maintenance_job_status_created", "maintenance_status", "created_at", "id"),
        SAIndex("ix_automation_maintenance_job_type_created", "maintenance_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    maintenance_key: str = Field(max_length=120, nullable=False, index=True)
    maintenance_type: str = Field(max_length=40, nullable=False, index=True)
    maintenance_status: str = Field(max_length=24, nullable=False, index=True)
    maintenance_scope: str = Field(max_length=80, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    maintenance_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationMaintenanceResult(SQLModel, table=True):
    __tablename__ = "automation_maintenance_results"
    __table_args__ = (
        UniqueConstraint("maintenance_job_id", "result_checksum", name="uq_automation_maintenance_result_checksum"),
        SAIndex("ix_automation_maintenance_result_job_created", "maintenance_job_id", "created_at", "id"),
        SAIndex("ix_automation_maintenance_result_status_created", "result_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    maintenance_job_id: int = Field(foreign_key="automation_maintenance_jobs.id", nullable=False, index=True)
    result_type: str = Field(max_length=32, nullable=False, index=True)
    result_status: str = Field(max_length=16, nullable=False, index=True)
    result_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationBatchArtifact(SQLModel, table=True):
    __tablename__ = "automation_batch_artifacts"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "maintenance_job_id", "artifact_type", "artifact_checksum", name="uq_automation_batch_artifact_type_checksum"),
        SAIndex("ix_automation_batch_artifact_batch_created", "batch_run_id", "created_at", "id"),
        SAIndex("ix_automation_batch_artifact_maintenance_created", "maintenance_job_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_run_id: int | None = Field(default=None, foreign_key="automation_batch_runs.id", nullable=True, index=True)
    maintenance_job_id: int | None = Field(default=None, foreign_key="automation_maintenance_jobs.id", nullable=True, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationBatchIssue(SQLModel, table=True):
    __tablename__ = "automation_batch_issues"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "maintenance_job_id", "issue_checksum", name="uq_automation_batch_issue_checksum"),
        SAIndex("ix_automation_batch_issue_batch_created", "batch_run_id", "created_at", "id"),
        SAIndex("ix_automation_batch_issue_maintenance_created", "maintenance_job_id", "created_at", "id"),
        SAIndex("ix_automation_batch_issue_type_created", "issue_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_run_id: int | None = Field(default=None, foreign_key="automation_batch_runs.id", nullable=True, index=True)
    maintenance_job_id: int | None = Field(default=None, foreign_key="automation_maintenance_jobs.id", nullable=True, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationBatchHistory(SQLModel, table=True):
    __tablename__ = "automation_batch_history"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "maintenance_job_id", "event_checksum", name="uq_automation_batch_history_checksum"),
        SAIndex("ix_automation_batch_history_batch_created", "batch_run_id", "created_at", "id"),
        SAIndex("ix_automation_batch_history_maintenance_created", "maintenance_job_id", "created_at", "id"),
        SAIndex("ix_automation_batch_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_run_id: int | None = Field(default=None, foreign_key="automation_batch_runs.id", nullable=True, index=True)
    maintenance_job_id: int | None = Field(default=None, foreign_key="automation_maintenance_jobs.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
