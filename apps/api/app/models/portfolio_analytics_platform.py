"""P67 Portfolio Analytics Platform models (read-only aggregates of P61–P66)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P67_SOURCE_VERSION = "P67-01-05"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P67PortfolioPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p67_portfolio_performance_snapshot"
    __table_args__ = (SAIndex("ix_p67_port_perf_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_estimated_value: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_unrealized_gain_pct: float = Field(default=0.0, nullable=False)
    total_realized_gain: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_realized_gain_pct: float = Field(default=0.0, nullable=False)
    average_roi_pct: float = Field(default=0.0, nullable=False)
    portfolio_cagr_pct: float | None = Field(default=None, nullable=True)
    best_performer_title: str = Field(default="", max_length=512, nullable=False)
    worst_performer_title: str = Field(default="", max_length=512, nullable=False)
    largest_position_title: str = Field(default="", max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P67_SOURCE_VERSION, max_length=32, nullable=False)


class P67PortfolioPerformanceItem(SQLModel, table=True):
    __tablename__ = "p67_portfolio_performance_item"
    __table_args__ = (SAIndex("ix_p67_port_perf_item_snap", "snapshot_id", "unrealized_gain_pct", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p67_portfolio_performance_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    series: str = Field(default="", max_length=255, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    estimated_value: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain_pct: float = Field(default=0.0, nullable=False)
    realized_gain: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    realized_gain_pct: float = Field(default=0.0, nullable=False)
    roi_pct: float = Field(default=0.0, nullable=False)
    notes_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P67CollectionAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p67_collection_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p67_coll_analytics_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_holdings: int = Field(default=0, nullable=False)
    concentration_score: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P67_SOURCE_VERSION, max_length=32, nullable=False)


class P67RecommendationPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p67_recommendation_performance_snapshot"
    __table_args__ = (SAIndex("ix_p67_rec_perf_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_tracked: int = Field(default=0, nullable=False)
    hit_rate_pct: float = Field(default=0.0, nullable=False)
    average_return_pct: float = Field(default=0.0, nullable=False)
    recommendation_roi_pct: float = Field(default=0.0, nullable=False)
    confidence_accuracy_pct: float = Field(default=0.0, nullable=False)
    best_recommendation_title: str = Field(default="", max_length=512, nullable=False)
    worst_recommendation_title: str = Field(default="", max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P67_SOURCE_VERSION, max_length=32, nullable=False)


class P67RecommendationPerformanceItem(SQLModel, table=True):
    __tablename__ = "p67_recommendation_performance_item"
    __table_args__ = (SAIndex("ix_p67_rec_perf_item_snap", "snapshot_id", "return_pct", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p67_recommendation_performance_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    cross_system_recommendation_id: int | None = Field(default=None, foreign_key="cross_system_recommendation.id", nullable=True)
    title: str = Field(default="", max_length=512, nullable=False)
    recommendation_type: str = Field(default="", max_length=16, nullable=False)
    priority_score: float = Field(default=0.0, nullable=False)
    confidence_score: float = Field(default=0.0, nullable=False)
    recommended: bool = Field(default=True, nullable=False)
    viewed: bool = Field(default=False, nullable=False)
    purchased: bool = Field(default=False, nullable=False)
    held: bool = Field(default=False, nullable=False)
    sold: bool = Field(default=False, nullable=False)
    outcome: str = Field(default="PENDING", max_length=24, nullable=False, index=True)
    return_pct: float = Field(default=0.0, nullable=False)
    notes_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P67GradingOpportunitySnapshot(SQLModel, table=True):
    __tablename__ = "p67_grading_opportunity_snapshot"
    __table_args__ = (SAIndex("ix_p67_grade_opp_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_candidates: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P67_SOURCE_VERSION, max_length=32, nullable=False)


class P67GradingOpportunityItem(SQLModel, table=True):
    __tablename__ = "p67_grading_opportunity_item"
    __table_args__ = (SAIndex("ix_p67_grade_opp_item_snap", "snapshot_id", "submission_priority", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p67_grading_opportunity_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    title: str = Field(default="", max_length=512, nullable=False)
    estimated_grade: str = Field(default="", max_length=32, nullable=False)
    submission_candidate_score: float = Field(default=0.0, nullable=False)
    estimated_roi_pct: float = Field(default=0.0, nullable=False)
    raw_value: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    graded_value: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    submission_priority: int = Field(default=0, nullable=False, index=True)
    notes_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P67InvestorDashboardSnapshot(SQLModel, table=True):
    __tablename__ = "p67_investor_dashboard_snapshot"
    __table_args__ = (SAIndex("ix_p67_investor_dash_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    collection_value: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    realized_gain: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    portfolio_health_score: float = Field(default=0.0, nullable=False)
    cards_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P67_SOURCE_VERSION, max_length=32, nullable=False)
