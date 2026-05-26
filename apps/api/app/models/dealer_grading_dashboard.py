"""P37-08 deterministic dealer grading dashboard."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DealerGradingDashboardSnapshot(SQLModel, table=True):
    __tablename__ = "dealer_grading_dashboard_snapshot"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_dealer_grading_dashboard_snapshot_owner_replay"),
        SAIndex("ix_dealer_grading_dashboard_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_dealer_grading_dashboard_snapshot_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    active_candidate_count: int = Field(default=0, nullable=False)
    ready_for_submission_count: int = Field(default=0, nullable=False)
    submitted_candidate_count: int = Field(default=0, nullable=False)
    graded_candidate_count: int = Field(default=0, nullable=False)
    elite_recommendation_count: int = Field(default=0, nullable=False)
    high_risk_candidate_count: int = Field(default=0, nullable=False)
    low_confidence_candidate_count: int = Field(default=0, nullable=False)
    average_estimated_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    average_risk_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    active_submission_batch_count: int = Field(default=0, nullable=False)
    grading_pipeline_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    estimated_total_submission_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    expected_total_profit: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerGradingDashboardMetric(SQLModel, table=True):
    __tablename__ = "dealer_grading_dashboard_metric"
    __table_args__ = (
        UniqueConstraint("dashboard_snapshot_id", "metric_key", name="uq_dealer_grading_dashboard_metric_snapshot_key"),
        SAIndex("ix_dealer_grading_dashboard_metric_snapshot", "dashboard_snapshot_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    dashboard_snapshot_id: int = Field(foreign_key="dealer_grading_dashboard_snapshot.id", nullable=False, index=True)
    metric_key: str = Field(max_length=80, nullable=False)
    metric_value_decimal: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    metric_value_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metric_metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerGradingDashboardAlert(SQLModel, table=True):
    __tablename__ = "dealer_grading_dashboard_alert"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "alert_replay_key", name="uq_dealer_grading_dashboard_alert_owner_replay"),
        SAIndex("ix_dealer_grading_dashboard_alert_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_dealer_grading_dashboard_alert_owner_dashboard", "owner_user_id", "dashboard_snapshot_id"),
        SAIndex("ix_dealer_grading_dashboard_alert_type_severity", "alert_type", "severity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    dashboard_snapshot_id: int = Field(foreign_key="dealer_grading_dashboard_snapshot.id", nullable=False, index=True)
    alert_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    alert_replay_key: str = Field(max_length=200, nullable=False)
    source_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True)
    source_submission_batch_id: int | None = Field(default=None, foreign_key="grading_submission_batch.id", nullable=True)
    source_recommendation_id: int | None = Field(default=None, foreign_key="grading_recommendation.id", nullable=True)
    message: str = Field(sa_column=Column(Text, nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerGradingDashboardFeedEvent(SQLModel, table=True):
    __tablename__ = "dealer_grading_dashboard_feed_event"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "deterministic_key", name="uq_dealer_grading_dashboard_feed_owner_key"),
        SAIndex("ix_dealer_grading_dashboard_feed_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    deterministic_key: str = Field(max_length=200, nullable=False)
    dashboard_snapshot_id: int | None = Field(default=None, foreign_key="dealer_grading_dashboard_snapshot.id", nullable=True)
    event_type: str = Field(max_length=40, nullable=False)
    source_id: int | None = Field(default=None, nullable=True)
    summary: str = Field(sa_column=Column(Text, nullable=False))
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
