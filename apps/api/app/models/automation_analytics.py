from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AutomationAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "automation_analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "snapshot_key", name="uq_automation_analytics_snapshot_owner_key"),
        SAIndex("ix_automation_analytics_snapshot_type_created", "analytics_type", "created_at", "id"),
        SAIndex("ix_automation_analytics_snapshot_status_created", "analytics_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, nullable=True, index=True)
    snapshot_key: str = Field(max_length=160, nullable=False, index=True)
    analytics_type: str = Field(max_length=32, nullable=False, index=True)
    analytics_scope: str = Field(max_length=80, nullable=False, index=True)
    analytics_status: str = Field(max_length=16, nullable=False, index=True)
    replay_safe: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    deterministic_ordering_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsMetric(SQLModel, table=True):
    __tablename__ = "automation_analytics_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "metric_key", name="uq_automation_analytics_metric_snapshot_key"),
        SAIndex("ix_automation_analytics_metric_category_rank", "snapshot_id", "metric_category", "metric_rank", "metric_key", "id"),
        SAIndex("ix_automation_analytics_metric_status_created", "metric_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_analytics_snapshots.id", nullable=False, index=True)
    metric_key: str = Field(max_length=120, nullable=False, index=True)
    metric_category: str = Field(max_length=24, nullable=False, index=True)
    metric_value: str = Field(max_length=512, nullable=False)
    metric_delta: str | None = Field(default=None, max_length=512, nullable=True)
    metric_status: str = Field(max_length=16, nullable=False, index=True)
    metric_rank: int = Field(nullable=False, index=True)
    metric_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsTrend(SQLModel, table=True):
    __tablename__ = "automation_analytics_trends"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "trend_key", name="uq_automation_analytics_trend_snapshot_key"),
        SAIndex("ix_automation_analytics_trend_type_created", "trend_type", "created_at", "id"),
        SAIndex("ix_automation_analytics_trend_direction_created", "trend_direction", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_analytics_snapshots.id", nullable=False, index=True)
    trend_key: str = Field(max_length=120, nullable=False, index=True)
    trend_type: str = Field(max_length=32, nullable=False, index=True)
    trend_direction: str = Field(max_length=16, nullable=False, index=True)
    historical_window: int = Field(nullable=False, index=True)
    trend_value: str = Field(max_length=512, nullable=False)
    trend_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsComparison(SQLModel, table=True):
    __tablename__ = "automation_analytics_comparisons"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "comparison_key", name="uq_automation_analytics_comparison_snapshot_key"),
        SAIndex("ix_automation_analytics_comparison_type_created", "comparison_type", "created_at", "id"),
        SAIndex("ix_automation_analytics_comparison_snapshot_created", "snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_analytics_snapshots.id", nullable=False, index=True)
    comparison_key: str = Field(max_length=120, nullable=False, index=True)
    comparison_type: str = Field(max_length=32, nullable=False, index=True)
    baseline_snapshot_id: int | None = Field(default=None, foreign_key="automation_analytics_snapshots.id", nullable=True, index=True)
    comparison_result_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    comparison_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsArtifact(SQLModel, table=True):
    __tablename__ = "automation_analytics_artifacts"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "artifact_type", "artifact_checksum", name="uq_automation_analytics_artifact_type_checksum"),
        SAIndex("ix_automation_analytics_artifact_snapshot_created", "snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_analytics_snapshots.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsIssue(SQLModel, table=True):
    __tablename__ = "automation_analytics_issues"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "issue_checksum", name="uq_automation_analytics_issue_checksum"),
        SAIndex("ix_automation_analytics_issue_type_created", "issue_type", "created_at", "id"),
        SAIndex("ix_automation_analytics_issue_snapshot_created", "snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="automation_analytics_snapshots.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AutomationAnalyticsHistory(SQLModel, table=True):
    __tablename__ = "automation_analytics_history"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "event_checksum", name="uq_automation_analytics_history_checksum"),
        SAIndex("ix_automation_analytics_history_snapshot_created", "snapshot_id", "created_at", "id"),
        SAIndex("ix_automation_analytics_history_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int | None = Field(default=None, foreign_key="automation_analytics_snapshots.id", nullable=True, index=True)
    comparison_id: int | None = Field(default=None, foreign_key="automation_analytics_comparisons.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    to_status: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
