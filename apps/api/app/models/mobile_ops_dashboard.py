from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MobileOpsSnapshot(SQLModel, table=True):
    __tablename__ = "mobile_ops_snapshots"
    __table_args__ = (
        SAIndex("ix_mobile_ops_snapshot_org_generated", "organization_id", "generated_at", "id"),
        SAIndex("ix_mobile_ops_snapshot_org_type_generated", "organization_id", "snapshot_type", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    snapshot_type: str = Field(max_length=40, nullable=False, index=True)
    snapshot_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileOpsMetric(SQLModel, table=True):
    __tablename__ = "mobile_ops_metrics"
    __table_args__ = (
        SAIndex("ix_mobile_ops_metric_org_generated", "organization_id", "generated_at", "id"),
        SAIndex("ix_mobile_ops_metric_org_key_generated", "organization_id", "metric_key", "generated_at", "id"),
        SAIndex("ix_mobile_ops_metric_org_period_generated", "organization_id", "metric_period", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    metric_key: str = Field(max_length=80, nullable=False, index=True)
    metric_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metric_period: str = Field(max_length=32, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MobileOpsDiagnostic(SQLModel, table=True):
    __tablename__ = "mobile_ops_diagnostics"
    __table_args__ = (
        SAIndex("ix_mobile_ops_diag_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_ops_diag_org_category_created", "organization_id", "diagnostic_category", "created_at", "id"),
        SAIndex("ix_mobile_ops_diag_org_status_created", "organization_id", "diagnostic_status", "created_at", "id"),
        SAIndex("ix_mobile_ops_diag_org_code_created", "organization_id", "diagnostic_code", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    diagnostic_category: str = Field(max_length=32, nullable=False, index=True)
    diagnostic_status: str = Field(max_length=16, nullable=False, index=True)
    diagnostic_code: str = Field(max_length=80, nullable=False, index=True)
    diagnostic_message: str = Field(max_length=1000, nullable=False)
    diagnostic_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MobileOpsEvent(SQLModel, table=True):
    __tablename__ = "mobile_ops_events"
    __table_args__ = (
        SAIndex("ix_mobile_ops_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mobile_ops_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_mobile_ops_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
