from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationDealerDashboardSnapshot(SQLModel, table=True):
    """P42-09 org-scoped dealer operations dashboard snapshot (append-only)."""

    __tablename__ = "organization_dealer_dashboard_snapshots"
    __table_args__ = (
        SAIndex("ix_org_dealer_dashboard_snapshot_org_generated", "organization_id", "generated_at", "id"),
        SAIndex("ix_org_dealer_dashboard_snapshot_org_type_generated", "organization_id", "snapshot_type", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    snapshot_type: str = Field(max_length=32, nullable=False, index=True)
    snapshot_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationDealerOperationalMetric(SQLModel, table=True):
    __tablename__ = "organization_dealer_operational_metrics"
    __table_args__ = (
        SAIndex("ix_org_dealer_metric_org_key_generated", "organization_id", "metric_key", "generated_at", "id"),
        SAIndex("ix_org_dealer_metric_org_period_generated", "organization_id", "metric_period", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    metric_key: str = Field(max_length=64, nullable=False, index=True)
    metric_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metric_period: str = Field(max_length=24, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationDealerDashboardEvent(SQLModel, table=True):
    __tablename__ = "organization_dealer_dashboard_events"
    __table_args__ = (
        SAIndex("ix_org_dealer_dashboard_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_dealer_dashboard_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
