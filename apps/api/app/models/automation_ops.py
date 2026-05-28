from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationOpsSnapshot(SQLModel, table=True):
    __tablename__ = "automation_ops_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "snapshot_key", name="uq_automation_ops_snapshot_owner_key"),
        SAIndex("ix_automation_ops_snapshot_type_created", "snapshot_type", "created_at", "id"),
        SAIndex("ix_automation_ops_snapshot_status_created", "snapshot_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    snapshot_key: str = Field(max_length=160, nullable=False, index=True)
    snapshot_type: str = Field(max_length=32, nullable=False, index=True)
    snapshot_status: str = Field(max_length=16, nullable=False, index=True)
    queue_depth: int = Field(default=0, nullable=False)
    active_workers: int = Field(default=0, nullable=False)
    active_workflows: int = Field(default=0, nullable=False)
    failed_jobs: int = Field(default=0, nullable=False)
    dead_letter_count: int = Field(default=0, nullable=False)
    replay_warning_count: int = Field(default=0, nullable=False)
    checksum_warning_count: int = Field(default=0, nullable=False)
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsMetric(SQLModel, table=True):
    __tablename__ = "automation_ops_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "metric_key", name="uq_automation_ops_metric_snapshot_key"),
        SAIndex("ix_automation_ops_metric_category_rank", "snapshot_id", "metric_category", "metric_rank", "metric_key", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_ops_snapshots.id", nullable=False, index=True)
    metric_key: str = Field(max_length=120, nullable=False, index=True)
    metric_category: str = Field(max_length=24, nullable=False, index=True)
    metric_value: str = Field(max_length=512, nullable=False)
    metric_status: str = Field(max_length=16, nullable=False, index=True)
    metric_rank: int = Field(nullable=False, index=True)
    metric_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsAudit(SQLModel, table=True):
    __tablename__ = "automation_ops_audits"
    __table_args__ = (
        UniqueConstraint("audit_key", name="uq_automation_ops_audit_key"),
        SAIndex("ix_automation_ops_audit_type_created", "audit_type", "created_at", "id"),
        SAIndex("ix_automation_ops_audit_status_created", "audit_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    snapshot_id: int | None = Field(default=None, foreign_key="automation_ops_snapshots.id", nullable=True, index=True)
    audit_key: str = Field(max_length=160, nullable=False, index=True)
    audit_type: str = Field(max_length=32, nullable=False, index=True)
    audit_status: str = Field(max_length=16, nullable=False, index=True)
    audit_scope: str = Field(max_length=80, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    audit_checksum: str = Field(max_length=64, nullable=False, index=True)
    audit_result_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsControl(SQLModel, table=True):
    __tablename__ = "automation_ops_controls"
    __table_args__ = (
        UniqueConstraint("control_key", name="uq_automation_ops_control_key"),
        SAIndex("ix_automation_ops_control_type_created", "control_type", "created_at", "id"),
        SAIndex("ix_automation_ops_control_status_created", "control_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    snapshot_id: int | None = Field(default=None, foreign_key="automation_ops_snapshots.id", nullable=True, index=True)
    control_key: str = Field(max_length=160, nullable=False, index=True)
    control_type: str = Field(max_length=32, nullable=False, index=True)
    control_status: str = Field(max_length=16, nullable=False, index=True)
    target_scope: str = Field(max_length=80, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    control_checksum: str = Field(max_length=64, nullable=False, index=True)
    control_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsArtifact(SQLModel, table=True):
    __tablename__ = "automation_ops_artifacts"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "artifact_type", "artifact_checksum", name="uq_automation_ops_artifact_type_checksum"),
        SAIndex("ix_automation_ops_artifact_snapshot_created", "snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_ops_snapshots.id", nullable=False, index=True)
    audit_id: int | None = Field(default=None, foreign_key="automation_ops_audits.id", nullable=True, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsIssue(SQLModel, table=True):
    __tablename__ = "automation_ops_issues"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "issue_checksum", name="uq_automation_ops_issue_checksum"),
        SAIndex("ix_automation_ops_issue_type_created", "issue_type", "created_at", "id"),
        SAIndex("ix_automation_ops_issue_snapshot_created", "snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_ops_snapshots.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationOpsHistory(SQLModel, table=True):
    __tablename__ = "automation_ops_history"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "event_checksum", name="uq_automation_ops_history_checksum"),
        SAIndex("ix_automation_ops_history_snapshot_created", "snapshot_id", "created_at", "id"),
        SAIndex("ix_automation_ops_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int | None = Field(default=None, foreign_key="automation_ops_snapshots.id", nullable=True, index=True)
    audit_id: int | None = Field(default=None, foreign_key="automation_ops_audits.id", nullable=True, index=True)
    control_id: int | None = Field(default=None, foreign_key="automation_ops_controls.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
