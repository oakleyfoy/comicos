"""P61 Demand Intelligence Platform models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

P61_SOURCE_VERSION = "P61-01"
P61_ENGINE_EPOCH = 1

REFRESH_STATUS_RUNNING = "RUNNING"
REFRESH_STATUS_SUCCESS = "SUCCESS"
REFRESH_STATUS_FAILED = "FAILED"
REFRESH_STATUS_PARTIAL = "PARTIAL"

CAPTURE_STATUS_PENDING = "PENDING"
CAPTURE_STATUS_RUNNING = "RUNNING"
CAPTURE_STATUS_CERTIFIED = "CERTIFIED"
CAPTURE_STATUS_FAILED = "FAILED"

TREND_RISING = "RISING"
TREND_STABLE = "STABLE"
TREND_FALLING = "FALLING"
TREND_INSUFFICIENT = "INSUFFICIENT_HISTORY"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DemandRefreshRun(SQLModel, table=True):
    __tablename__ = "demand_refresh_run"
    __table_args__ = (SAIndex("ix_demand_refresh_run_started", "started_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    trigger_type: str = Field(max_length=48, nullable=False, index=True)
    scope: str = Field(max_length=32, nullable=False, index=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default=REFRESH_STATUS_RUNNING, max_length=24, nullable=False, index=True)
    profiles_updated: int = Field(default=0, nullable=False)
    issues_refreshed: int = Field(default=0, nullable=False)
    signals_appended: int = Field(default=0, nullable=False)
    source_version: str = Field(default=P61_SOURCE_VERSION, max_length=32, nullable=False)
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class IssueDemandSnapshot(SQLModel, table=True):
    __tablename__ = "issue_demand_snapshot"
    __table_args__ = (
        UniqueConstraint("source_name", "external_issue_id", name="uq_issue_demand_snapshot_source_external"),
        SAIndex("ix_issue_demand_snapshot_release", "release_issue_id", "combined_demand_score"),
        SAIndex("ix_issue_demand_snapshot_refreshed", "refreshed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(max_length=64, nullable=False, index=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    pull_count: int | None = Field(default=None, nullable=True)
    want_count: int | None = Field(default=None, nullable=True)
    community_demand_score: float = Field(default=0.0, nullable=False, index=True)
    entity_rollup_score: float = Field(default=50.0, nullable=False)
    combined_demand_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.5, nullable=False)
    signal_sources_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P61_SOURCE_VERSION, max_length=32, nullable=False)
    refreshed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IssueDemandObservation(SQLModel, table=True):
    __tablename__ = "issue_demand_observation"
    __table_args__ = (SAIndex("ix_issue_demand_obs_external_observed", "external_issue_id", "observed_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    observed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    pull_count: int | None = Field(default=None, nullable=True)
    want_count: int | None = Field(default=None, nullable=True)
    community_demand_score: float = Field(default=0.0, nullable=False)
    capture_run_id: int | None = Field(default=None, nullable=True, index=True)


class DemandVelocitySnapshot(SQLModel, table=True):
    __tablename__ = "demand_velocity_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "release_issue_id",
            "external_issue_id",
            "window_days",
            name="uq_demand_velocity_issue_window",
        ),
        SAIndex("ix_demand_velocity_score", "velocity_score", "computed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    window_days: int = Field(default=7, nullable=False, index=True)
    pull_delta: float = Field(default=0.0, nullable=False)
    want_delta: float = Field(default=0.0, nullable=False)
    combined_score_delta: float = Field(default=0.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False, index=True)
    acceleration_score: float = Field(default=0.0, nullable=False)
    trend_label: str = Field(default=TREND_INSUFFICIENT, max_length=32, nullable=False, index=True)
    confidence_score: float = Field(default=0.25, nullable=False)
    source_version: str = Field(default=P61_SOURCE_VERSION, max_length=32, nullable=False)
    computed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SpecOpportunitySnapshot(SQLModel, table=True):
    __tablename__ = "spec_opportunity_snapshot"
    __table_args__ = (SAIndex("ix_spec_opportunity_snapshot_owner", "owner_user_id", "snapshot_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    engine_epoch: int = Field(default=P61_ENGINE_EPOCH, nullable=False, index=True)
    row_count: int = Field(default=0, nullable=False)
    source_version: str = Field(default=P61_SOURCE_VERSION, max_length=32, nullable=False)


class SpecOpportunityRow(SQLModel, table=True):
    __tablename__ = "spec_opportunity_row"
    __table_args__ = (
        SAIndex("ix_spec_opportunity_row_snapshot_rank", "snapshot_id", "rank", "id"),
        SAIndex("ix_spec_opportunity_row_owner_issue", "owner_user_id", "release_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="spec_opportunity_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    opportunity_score: float = Field(default=0.0, nullable=False, index=True)
    spec_baseline_score: float | None = Field(default=None, nullable=True)
    demand_score: float = Field(default=0.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False)
    preference_fit_score: float = Field(default=50.0, nullable=False)
    horizon_bucket: str = Field(default="FORWARD", max_length=32, nullable=False, index=True)
    rationale_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    rank: int = Field(default=0, nullable=False, index=True)


class WeeklyDemandCaptureSchedule(SQLModel, table=True):
    __tablename__ = "weekly_demand_capture_schedule"
    __table_args__ = (UniqueConstraint("release_date", name="uq_weekly_demand_capture_release_date"),)

    id: int | None = Field(default=None, primary_key=True)
    release_date: date = Field(nullable=False, index=True)
    status: str = Field(default=CAPTURE_STATUS_PENDING, max_length=24, nullable=False, index=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    certification_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    sync_run_id: int | None = Field(default=None, nullable=True, index=True)
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class WeeklyDemandCaptureEvent(SQLModel, table=True):
    __tablename__ = "weekly_demand_capture_event"
    __table_args__ = (SAIndex("ix_weekly_demand_capture_event_schedule", "schedule_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="weekly_demand_capture_schedule.id", nullable=False, index=True)
    step: str = Field(max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
