"""P36-07 deterministic dealer dashboard (operational truth; no predictive layer)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DealerDashboardSnapshot(SQLModel, table=True):
    __tablename__ = "dealer_dashboard_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "replay_key",
            name="uq_dealer_dashboard_snapshot_owner_replay",
        ),
        SAIndex("ix_dealer_dashboard_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_dealer_dashboard_snapshot_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)

    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    active_listing_count: int = Field(default=0, nullable=False)
    export_ready_count: int = Field(default=0, nullable=False)
    incomplete_listing_count: int = Field(default=0, nullable=False)
    stale_listing_count: int = Field(default=0, nullable=False)
    active_convention_count: int = Field(default=0, nullable=False)
    assigned_convention_inventory_count: int = Field(default=0, nullable=False)
    open_sale_session_count: int = Field(default=0, nullable=False)

    gross_sales_30d: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 2), nullable=False))
    net_sales_30d: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 2), nullable=False))
    realized_profit_30d: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 2), nullable=False))

    liquidity_high_count: int = Field(default=0, nullable=False)
    liquidity_low_count: int = Field(default=0, nullable=False)
    export_run_count_30d: int = Field(default=0, nullable=False)
    failed_export_count_30d: int = Field(default=0, nullable=False)

    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerDashboardMetric(SQLModel, table=True):
    __tablename__ = "dealer_dashboard_metric"
    __table_args__ = (
        UniqueConstraint(
            "dashboard_snapshot_id",
            "metric_key",
            name="uq_dealer_dashboard_metric_snapshot_key",
        ),
        SAIndex("ix_dealer_dashboard_metric_snapshot", "dashboard_snapshot_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    dashboard_snapshot_id: int = Field(foreign_key="dealer_dashboard_snapshot.id", nullable=False, index=True)
    metric_key: str = Field(max_length=80, nullable=False)
    metric_value_decimal: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    metric_value_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metric_metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerDashboardAlert(SQLModel, table=True):
    __tablename__ = "dealer_dashboard_alert"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "alert_replay_key",
            name="uq_dealer_dashboard_alert_owner_replay_key",
        ),
        SAIndex("ix_dealer_dashboard_alert_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_dealer_dashboard_alert_owner_dashboard", "owner_user_id", "dashboard_snapshot_id"),
        SAIndex("ix_dealer_dashboard_alert_type_severity", "alert_type", "severity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    dashboard_snapshot_id: int = Field(foreign_key="dealer_dashboard_snapshot.id", nullable=False, index=True)

    alert_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    alert_replay_key: str = Field(max_length=160, nullable=False)

    source_listing_id: int | None = Field(default=None, foreign_key="listing.id", nullable=True)
    source_inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    source_export_run_id: int | None = Field(default=None, foreign_key="listing_export_run.id", nullable=True)
    source_convention_event_id: int | None = Field(default=None, foreign_key="convention_event.id", nullable=True)

    message: str = Field(sa_column=Column(Text, nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerDashboardFeedEvent(SQLModel, table=True):
    __tablename__ = "dealer_dashboard_feed_event"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "deterministic_key",
            name="uq_dealer_dashboard_feed_event_owner_key",
        ),
        SAIndex("ix_dealer_dashboard_feed_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    deterministic_key: str = Field(max_length=192, nullable=False)

    dashboard_snapshot_id: int | None = Field(
        default=None,
        foreign_key="dealer_dashboard_snapshot.id",
        nullable=True,
        index=True,
    )
    event_type: str = Field(max_length=40, nullable=False, index=True)

    source_id: int | None = Field(default=None, nullable=True, index=True)
    summary: str = Field(sa_column=Column(Text, nullable=False))
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
