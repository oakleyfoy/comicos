"""P63 Market Intelligence Platform models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P63_MARKET_SOURCE_VERSION = "P63-01-04"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PERF_STRONG_GAIN = "STRONG_GAIN"
PERF_MODEST_GAIN = "MODEST_GAIN"
PERF_FLAT = "FLAT"
PERF_DOWN = "DOWN"
PERF_UNKNOWN = "UNKNOWN"

SELL_ACTION_SELL_NOW = "SELL_NOW"
SELL_ACTION_CONSIDER = "CONSIDER_SELLING"
SELL_ACTION_HOLD = "HOLD"
SELL_ACTION_GRADE_FIRST = "GRADE_FIRST"
SELL_ACTION_WATCH = "WATCH"

SELL_STATUS_NEW = "NEW"
SELL_STATUS_REVIEWED = "REVIEWED"
SELL_STATUS_LISTED = "LISTED"
SELL_STATUS_SOLD = "SOLD"
SELL_STATUS_DISMISSED = "DISMISSED"

ACQ_ACTION_BUY_NOW = "BUY_NOW"
ACQ_ACTION_WATCH_PRICE = "WATCH_PRICE"
ACQ_ACTION_WANT_LIST = "ADD_TO_WANT_LIST"
ACQ_ACTION_WAIT = "WAIT"
ACQ_ACTION_PASS = "PASS"

ACQ_STATUS_NEW = "NEW"
ACQ_STATUS_WATCHING = "WATCHING"
ACQ_STATUS_BOUGHT = "BOUGHT"
ACQ_STATUS_DISMISSED = "DISMISSED"

MARKET_SIGNAL_SCOPES = ("OWNER", "CATALOG")


class PortfolioPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_performance_snapshot"
    __table_args__ = (SAIndex("ix_portfolio_perf_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    total_cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_current_value: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    total_unrealized_gain_pct: float = Field(default=0.0, nullable=False)
    top_gainers_count: int = Field(default=0, nullable=False)
    top_losers_count: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P63_MARKET_SOURCE_VERSION, max_length=32, nullable=False)


class PortfolioPerformanceItem(SQLModel, table=True):
    __tablename__ = "portfolio_performance_item"
    __table_args__ = (SAIndex("ix_portfolio_perf_item_snap_gain", "snapshot_id", "unrealized_gain_pct", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="portfolio_performance_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    quantity: int = Field(default=1, nullable=False)
    cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    current_value: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain_pct: float = Field(default=0.0, nullable=False)
    demand_score: float = Field(default=50.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False)
    recommendation_score: float = Field(default=50.0, nullable=False)
    performance_tier: str = Field(default=PERF_UNKNOWN, max_length=24, nullable=False, index=True)
    notes_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class SellSignalSnapshot(SQLModel, table=True):
    __tablename__ = "sell_signal_snapshot"
    __table_args__ = (SAIndex("ix_sell_signal_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    strong_sell_count: int = Field(default=0, nullable=False)
    consider_sell_count: int = Field(default=0, nullable=False)
    hold_count: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P63_MARKET_SOURCE_VERSION, max_length=32, nullable=False)


class SellSignalItem(SQLModel, table=True):
    __tablename__ = "sell_signal_item"
    __table_args__ = (SAIndex("ix_sell_signal_item_snap_score", "snapshot_id", "sell_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="sell_signal_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    sell_score: float = Field(default=0.0, nullable=False, index=True)
    hold_score: float = Field(default=0.0, nullable=False)
    current_value: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    cost_basis: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    unrealized_gain_pct: float = Field(default=0.0, nullable=False)
    demand_score: float = Field(default=50.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False)
    quantity_owned: int = Field(default=1, nullable=False)
    grade_status: str = Field(default="raw", max_length=32, nullable=False)
    sell_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    recommended_action: str = Field(default=SELL_ACTION_HOLD, max_length=24, nullable=False, index=True)
    confidence: str = Field(default="MEDIUM", max_length=16, nullable=False)
    status: str = Field(default=SELL_STATUS_NEW, max_length=16, nullable=False, index=True)


class AcquisitionOpportunitySnapshot(SQLModel, table=True):
    __tablename__ = "acquisition_opportunity_snapshot"
    __table_args__ = (SAIndex("ix_acq_opp_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    high_priority_count: int = Field(default=0, nullable=False)
    watch_count: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P63_MARKET_SOURCE_VERSION, max_length=32, nullable=False)


class AcquisitionOpportunityItem(SQLModel, table=True):
    __tablename__ = "acquisition_opportunity_item"
    __table_args__ = (SAIndex("ix_acq_opp_item_snap_score", "snapshot_id", "opportunity_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="acquisition_opportunity_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    opportunity_score: float = Field(default=0.0, nullable=False, index=True)
    demand_score: float = Field(default=50.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False)
    spec_score: float = Field(default=50.0, nullable=False)
    recommendation_score: float = Field(default=50.0, nullable=False)
    estimated_market_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    target_buy_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    action: str = Field(default=ACQ_ACTION_WAIT, max_length=24, nullable=False, index=True)
    status: str = Field(default=ACQ_STATUS_NEW, max_length=16, nullable=False, index=True)


class MarketSignalSnapshot(SQLModel, table=True):
    __tablename__ = "market_signal_snapshot"
    __table_args__ = (SAIndex("ix_market_signal_snap_scope_gen", "scope", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    scope: str = Field(default="OWNER", max_length=16, nullable=False, index=True)
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P63_MARKET_SOURCE_VERSION, max_length=32, nullable=False)


class MarketSignalItem(SQLModel, table=True):
    __tablename__ = "market_signal_item"
    __table_args__ = (SAIndex("ix_market_signal_item_snap_score", "snapshot_id", "market_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="market_signal_snapshot.id", nullable=False, index=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    market_score: float = Field(default=50.0, nullable=False, index=True)
    demand_score: float = Field(default=50.0, nullable=False)
    velocity_score: float = Field(default=50.0, nullable=False)
    price_score: float = Field(default=50.0, nullable=False)
    liquidity_score: float = Field(default=50.0, nullable=False)
    opportunity_score: float = Field(default=50.0, nullable=False)
    risk_score: float = Field(default=50.0, nullable=False)
    signal_type: str = Field(default="HOLD_STRENGTH", max_length=32, nullable=False, index=True)
    signal_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    confidence: str = Field(default="MEDIUM", max_length=16, nullable=False)
    notes_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
