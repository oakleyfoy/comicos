"""P81-03 discovery analytics snapshot persistence."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P81DiscoveryAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p81_discovery_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p81_disc_analytics_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    activity_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    conversion_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81DiscoveryOpportunityPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p81_discovery_opportunity_performance_snapshot"
    __table_args__ = (SAIndex("ix_p81_disc_opp_perf_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    category_performance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    roi_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81DiscoveryAlertPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p81_discovery_alert_performance_snapshot"
    __table_args__ = (SAIndex("ix_p81_disc_alert_perf_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    engagement_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    conversion_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81DiscoveryRoiSnapshot(SQLModel, table=True):
    __tablename__ = "p81_discovery_roi_snapshot"
    __table_args__ = (SAIndex("ix_p81_disc_roi_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    fmv_growth_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    portfolio_roi_pct: float = Field(default=0.0, nullable=False)
    performance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
