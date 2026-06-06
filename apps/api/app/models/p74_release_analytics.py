"""P74-03 release outcome and analytics snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P74_ANALYTICS_SOURCE = "p74-03"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P74ReleaseOutcome(SQLModel, table=True):
    __tablename__ = "p74_release_outcome"
    __table_args__ = (
        SAIndex("ix_p74_release_outcome_owner_issue", "owner_user_id", "release_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    recommended_quantity: int = Field(default=0, nullable=False)
    ordered_quantity: int = Field(default=0, nullable=False)
    actual_quantity_purchased: int = Field(default=0, nullable=False)
    foc_date: date | None = Field(default=None, nullable=True)
    release_date: date | None = Field(default=None, nullable=True)
    market_performance_pct: float = Field(default=0.0, nullable=False)
    inventory_performance_pct: float = Field(default=0.0, nullable=False)
    actual_profit: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(14, 2), nullable=False))
    actual_roi_pct: float = Field(default=0.0, nullable=False)
    outcome_status: str = Field(max_length=24, nullable=False, index=True)
    purchase_action: str = Field(default="", max_length=16, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    recorded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P74ReleaseAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p74_release_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p74_rel_analytics_owner", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    outcomes_tracked: int = Field(default=0, nullable=False)
    success_count: int = Field(default=0, nullable=False)
    failure_count: int = Field(default=0, nullable=False)
    platform_confidence_pct: float = Field(default=0.0, nullable=False)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P74_ANALYTICS_SOURCE, max_length=32, nullable=False)


class P74FocPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p74_foc_performance_snapshot"
    __table_args__ = (SAIndex("ix_p74_foc_perf_owner", "owner_user_id", "analytics_snapshot_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p74_release_analytics_snapshot.id", nullable=False, index=True)
    accuracy_rate_pct: float = Field(default=0.0, nullable=False)
    upgrade_accuracy_pct: float = Field(default=0.0, nullable=False)
    downgrade_accuracy_pct: float = Field(default=0.0, nullable=False)
    missed_opportunity_rate_pct: float = Field(default=0.0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P74_ANALYTICS_SOURCE, max_length=32, nullable=False)


class P74QuantityRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "p74_quantity_recommendation_snapshot"
    __table_args__ = (SAIndex("ix_p74_qty_rec_owner", "owner_user_id", "analytics_snapshot_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p74_release_analytics_snapshot.id", nullable=False, index=True)
    success_rate_pct: float = Field(default=0.0, nullable=False)
    failure_rate_pct: float = Field(default=0.0, nullable=False)
    average_roi_pct: float = Field(default=0.0, nullable=False)
    median_roi_pct: float = Field(default=0.0, nullable=False)
    by_action_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P74_ANALYTICS_SOURCE, max_length=32, nullable=False)


class P74ReleaseCategorySnapshot(SQLModel, table=True):
    __tablename__ = "p74_release_category_snapshot"
    __table_args__ = (
        SAIndex("ix_p74_rel_cat_snap", "analytics_snapshot_id", "category_key", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analytics_snapshot_id: int = Field(foreign_key="p74_release_analytics_snapshot.id", nullable=False, index=True)
    category_key: str = Field(max_length=48, nullable=False, index=True)
    sample_count: int = Field(default=0, nullable=False)
    success_rate_pct: float = Field(default=0.0, nullable=False)
    average_roi_pct: float = Field(default=0.0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P74_ANALYTICS_SOURCE, max_length=32, nullable=False)
