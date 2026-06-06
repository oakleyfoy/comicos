"""P71 Sell Intelligence Platform models (read-only recommendations)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P71_SOURCE_VERSION = "P71-01-05"

EXIT_SELL_NOW = "SELL_NOW"
EXIT_HOLD = "HOLD"
EXIT_TRIM = "TRIM_POSITION"
EXIT_WATCH = "WATCH"
EXIT_GRADE_THEN_SELL = "GRADE_THEN_SELL"

LISTING_AUCTION = "AUCTION"
LISTING_BIN = "BUY_IT_NOW"
LISTING_EITHER = "EITHER"

LIQ_HIGH = "HIGH"
LIQ_MEDIUM = "MEDIUM"
LIQ_LOW = "LOW"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P71ExitRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "p71_exit_recommendation_snapshot"
    __table_args__ = (SAIndex("ix_p71_exit_rec_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P71_SOURCE_VERSION, max_length=32, nullable=False)


class P71ExitRecommendationItem(SQLModel, table=True):
    __tablename__ = "p71_exit_recommendation_item"
    __table_args__ = (SAIndex("ix_p71_exit_rec_item_snap", "snapshot_id", "exit_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p71_exit_recommendation_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    recommendation: str = Field(default=EXIT_HOLD, max_length=32, nullable=False, index=True)
    exit_score: float = Field(default=0.0, nullable=False)
    exit_confidence: float = Field(default=0.0, nullable=False)
    primary_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    secondary_reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P71ListingRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "p71_listing_recommendation_snapshot"
    __table_args__ = (SAIndex("ix_p71_listing_rec_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P71_SOURCE_VERSION, max_length=32, nullable=False)


class P71ListingRecommendationItem(SQLModel, table=True):
    __tablename__ = "p71_listing_recommendation_item"
    __table_args__ = (SAIndex("ix_p71_listing_rec_item_snap", "snapshot_id", "expected_profit", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p71_listing_recommendation_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    suggested_bin: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    suggested_auction_start: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_sale_low: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_sale_high: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_profit: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    expected_roi_pct: float = Field(default=0.0, nullable=False)
    expected_days_to_sell: float = Field(default=0.0, nullable=False)
    listing_recommendation: str = Field(default=LISTING_EITHER, max_length=16, nullable=False)
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P71LiquiditySnapshot(SQLModel, table=True):
    __tablename__ = "p71_liquidity_snapshot"
    __table_args__ = (SAIndex("ix_p71_liquidity_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P71_SOURCE_VERSION, max_length=32, nullable=False)


class P71LiquidityItem(SQLModel, table=True):
    __tablename__ = "p71_liquidity_item"
    __table_args__ = (SAIndex("ix_p71_liquidity_item_snap", "snapshot_id", "liquidity_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p71_liquidity_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    liquidity_band: str = Field(default=LIQ_MEDIUM, max_length=16, nullable=False, index=True)
    liquidity_score: float = Field(default=0.0, nullable=False)
    sales_velocity: float = Field(default=0.0, nullable=False)
    observation_count: int = Field(default=0, nullable=False)
    demand_strength: float = Field(default=0.0, nullable=False)
    market_confidence: float = Field(default=0.0, nullable=False)
    days_to_sell_estimate: float = Field(default=0.0, nullable=False)
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P71ExitQueueSnapshot(SQLModel, table=True):
    __tablename__ = "p71_exit_queue_snapshot"
    __table_args__ = (SAIndex("ix_p71_exit_queue_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P71_SOURCE_VERSION, max_length=32, nullable=False)


class P71ExitQueueItem(SQLModel, table=True):
    __tablename__ = "p71_exit_queue_item"
    __table_args__ = (SAIndex("ix_p71_exit_queue_item_snap", "snapshot_id", "priority", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="p71_exit_queue_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    priority: int = Field(default=0, nullable=False, index=True)
    expected_profit: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    expected_roi_pct: float = Field(default=0.0, nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    recommended_action: str = Field(default=EXIT_HOLD, max_length=32, nullable=False)
    target_price: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    expected_days: float = Field(default=0.0, nullable=False)
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P71InvestorSellDashboardSnapshot(SQLModel, table=True):
    __tablename__ = "p71_investor_sell_dashboard_snapshot"
    __table_args__ = (SAIndex("ix_p71_sell_dash_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    expected_realized_profit: float = Field(default=0.0, sa_column=Column(Numeric(14, 2), nullable=False))
    cards_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P71_SOURCE_VERSION, max_length=32, nullable=False)
