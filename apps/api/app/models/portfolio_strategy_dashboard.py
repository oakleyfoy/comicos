"""P38-07 deterministic portfolio strategy dashboard."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioStrategyDashboardSnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_strategy_dashboard_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "replay_key",
            name="uq_portfolio_strategy_dashboard_snapshot_owner_replay",
        ),
        SAIndex("ix_portfolio_strategy_dashboard_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_portfolio_strategy_dashboard_snapshot_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    portfolio_count: int = Field(default=0, nullable=False)
    total_portfolio_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_cost_basis: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_realized_sales: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    diversification_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    liquidity_efficiency_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    concentration_risk_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    dead_capital_estimate: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    duplicate_cluster_count: int = Field(default=0, nullable=False)
    overexposed_category_count: int = Field(default=0, nullable=False)
    hold_recommendation_count: int = Field(default=0, nullable=False)
    sell_recommendation_count: int = Field(default=0, nullable=False)
    reduce_exposure_count: int = Field(default=0, nullable=False)
    acquisition_opportunity_count: int = Field(default=0, nullable=False)
    elite_acquisition_count: int = Field(default=0, nullable=False)
    grading_candidate_count: int = Field(default=0, nullable=False)
    liquid_inventory_percentage: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    illiquid_inventory_percentage: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))

    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioStrategyDashboardMetric(SQLModel, table=True):
    __tablename__ = "portfolio_strategy_dashboard_metric"
    __table_args__ = (
        UniqueConstraint(
            "dashboard_snapshot_id",
            "metric_key",
            name="uq_portfolio_strategy_dashboard_metric_snapshot_key",
        ),
        SAIndex("ix_portfolio_strategy_dashboard_metric_snapshot", "dashboard_snapshot_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    dashboard_snapshot_id: int = Field(
        foreign_key="portfolio_strategy_dashboard_snapshot.id",
        nullable=False,
        index=True,
    )
    metric_key: str = Field(max_length=80, nullable=False)
    metric_value_decimal: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    metric_value_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metric_metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioStrategyDashboardAlert(SQLModel, table=True):
    __tablename__ = "portfolio_strategy_dashboard_alert"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "alert_replay_key",
            name="uq_portfolio_strategy_dashboard_alert_owner_replay",
        ),
        SAIndex("ix_portfolio_strategy_dashboard_alert_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_portfolio_strategy_dashboard_alert_type_severity", "alert_type", "severity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    alert_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    alert_replay_key: str = Field(max_length=200, nullable=False)
    source_portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    source_inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    source_snapshot_id: int | None = Field(default=None, nullable=True, index=True)
    message: str = Field(sa_column=Column(Text, nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioStrategyDashboardFeedEvent(SQLModel, table=True):
    __tablename__ = "portfolio_strategy_dashboard_feed_event"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "deterministic_key",
            name="uq_portfolio_strategy_dashboard_feed_owner_key",
        ),
        SAIndex("ix_portfolio_strategy_dashboard_feed_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    deterministic_key: str = Field(max_length=200, nullable=False)
    dashboard_snapshot_id: int | None = Field(
        default=None,
        foreign_key="portfolio_strategy_dashboard_snapshot.id",
        nullable=True,
        index=True,
    )
    event_type: str = Field(max_length=40, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    summary: str = Field(sa_column=Column(Text, nullable=False))
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
