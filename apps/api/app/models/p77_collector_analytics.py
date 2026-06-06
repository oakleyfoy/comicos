"""P77-03 collector analytics snapshot persistence."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel

P77_ANALYTICS_SOURCE_VERSION = "p77-03"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P77CollectorAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p77_collector_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p77_analytics_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    profile_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    goal_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    personalization_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    assistant_metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P77RecommendationAdjustmentSnapshot(SQLModel, table=True):
    __tablename__ = "p77_recommendation_adjustment_snapshot"
    __table_args__ = (SAIndex("ix_p77_adj_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    recommendations_evaluated: int = Field(default=0, nullable=False)
    recommendations_adjusted: int = Field(default=0, nullable=False)
    adjustment_rate_pct: float = Field(default=0.0, nullable=False)
    category_breakdown_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    sample_adjustments_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class P77BudgetPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p77_budget_performance_snapshot"
    __table_args__ = (SAIndex("ix_p77_budget_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    monthly_budget: float = Field(default=0.0, nullable=False)
    monthly_spend: float = Field(default=0.0, nullable=False)
    utilization_percent: float = Field(default=0.0, nullable=False)
    budget_state: str = Field(default="GREEN", max_length=8, nullable=False)
    category_spend_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    forecast_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    compliance_score: float = Field(default=100.0, nullable=False)
