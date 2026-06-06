"""P79-03 storage analytics and health snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P79_ANALYTICS_SOURCE = "p79-03"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P79StorageAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p79_storage_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p79_stor_analytics_owner", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_locations: int = Field(default=0, nullable=False)
    total_boxes: int = Field(default=0, nullable=False)
    total_capacity: int = Field(default=0, nullable=False)
    used_capacity: int = Field(default=0, nullable=False)
    available_capacity: int = Field(default=0, nullable=False)
    utilization_pct: float = Field(default=0.0, nullable=False)
    assigned_inventory_count: int = Field(default=0, nullable=False)
    unassigned_inventory_count: int = Field(default=0, nullable=False)
    over_capacity_boxes: int = Field(default=0, nullable=False)
    inactive_locations: int = Field(default=0, nullable=False)
    forecast_risk: str = Field(default="LOW_RISK", max_length=16, nullable=False)
    estimated_months_until_full: float | None = Field(default=None, nullable=True)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P79_ANALYTICS_SOURCE, max_length=32, nullable=False)


class P79StorageUtilizationSnapshot(SQLModel, table=True):
    __tablename__ = "p79_storage_utilization_snapshot"
    __table_args__ = (
        SAIndex("ix_p79_stor_util_snap", "analytics_snapshot_id", "group_kind", "group_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p79_storage_analytics_snapshot.id", nullable=False, index=True)
    group_kind: str = Field(max_length=24, nullable=False, index=True)
    group_key: str = Field(max_length=128, nullable=False)
    entity_id: int | None = Field(default=None, nullable=True)
    utilization_pct: float = Field(default=0.0, nullable=False)
    used_capacity: int = Field(default=0, nullable=False)
    total_capacity: int = Field(default=0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79StorageAuditPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p79_storage_audit_performance_snapshot"
    __table_args__ = (SAIndex("ix_p79_stor_audit_perf", "analytics_snapshot_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p79_storage_analytics_snapshot.id", nullable=False, index=True)
    audits_started: int = Field(default=0, nullable=False)
    audits_completed: int = Field(default=0, nullable=False)
    average_verification_rate_pct: float = Field(default=0.0, nullable=False)
    missing_books_found: int = Field(default=0, nullable=False)
    unexpected_books_found: int = Field(default=0, nullable=False)
    duplicate_assignments_found: int = Field(default=0, nullable=False)
    moved_books: int = Field(default=0, nullable=False)
    audit_accuracy_rate_pct: float = Field(default=0.0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79StorageHealthSnapshot(SQLModel, table=True):
    __tablename__ = "p79_storage_health_snapshot"
    __table_args__ = (SAIndex("ix_p79_stor_health_snap", "analytics_snapshot_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p79_storage_analytics_snapshot.id", nullable=False, index=True)
    health_score: int = Field(default=0, nullable=False)
    health_status: str = Field(default="HEALTHY", max_length=16, nullable=False)
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
