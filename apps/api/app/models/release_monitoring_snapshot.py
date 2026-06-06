"""P74-01 release monitoring analytics snapshots (foundation only)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel

from app.models.release_event_history import P74_SOURCE_VERSION


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P74ReleaseMonitoringSnapshot(SQLModel, table=True):
    __tablename__ = "p74_release_monitoring_snapshot"
    __table_args__ = (
        SAIndex("ix_p74_release_mon_snap_owner", "owner_user_id", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    upcoming_total: int = Field(default=0, nullable=False)
    this_week_count: int = Field(default=0, nullable=False)
    next_week_count: int = Field(default=0, nullable=False)
    next_30_days_count: int = Field(default=0, nullable=False)
    next_90_days_count: int = Field(default=0, nullable=False)
    windows_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P74_SOURCE_VERSION, max_length=32, nullable=False)


class P74ReleaseChangeSnapshot(SQLModel, table=True):
    __tablename__ = "p74_release_change_snapshot"
    __table_args__ = (
        SAIndex("ix_p74_release_chg_snap_owner", "owner_user_id", "monitoring_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    monitoring_snapshot_id: int = Field(
        foreign_key="p74_release_monitoring_snapshot.id",
        nullable=False,
        index=True,
    )
    changes_total: int = Field(default=0, nullable=False)
    discoveries_total: int = Field(default=0, nullable=False)
    removals_total: int = Field(default=0, nullable=False)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P74_SOURCE_VERSION, max_length=32, nullable=False)


class P74VariantMonitoringSnapshot(SQLModel, table=True):
    __tablename__ = "p74_variant_monitoring_snapshot"
    __table_args__ = (
        SAIndex("ix_p74_variant_mon_snap_owner", "owner_user_id", "monitoring_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    monitoring_snapshot_id: int = Field(
        foreign_key="p74_release_monitoring_snapshot.id",
        nullable=False,
        index=True,
    )
    variants_added: int = Field(default=0, nullable=False)
    ratio_variants_added: int = Field(default=0, nullable=False)
    incentive_variants_added: int = Field(default=0, nullable=False)
    late_variants_added: int = Field(default=0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P74_SOURCE_VERSION, max_length=32, nullable=False)
