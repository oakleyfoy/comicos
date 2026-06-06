"""P70-06 market refresh history and FMV trend foundation."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P70_SOURCE_VERSION = "P70-06"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P70MarketRefreshRun(SQLModel, table=True):
    __tablename__ = "p70_market_refresh_run"
    __table_args__ = (SAIndex("ix_p70_refresh_owner_started", "owner_user_id", "started_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    trigger_type: str = Field(default="SCHEDULED", max_length=24, nullable=False, index=True)
    status: str = Field(default="COMPLETED", max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    target_copy_count: int = Field(default=0, nullable=False)
    books_refreshed: int = Field(default=0, nullable=False)
    comps_fetched: int = Field(default=0, nullable=False)
    fmv_snapshots_generated: int = Field(default=0, nullable=False)
    failure_count: int = Field(default=0, nullable=False)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P70MarketFmvTrendPoint(SQLModel, table=True):
    __tablename__ = "p70_market_fmv_trend_point"
    __table_args__ = (
        SAIndex("ix_p70_trend_owner_copy_date", "owner_user_id", "inventory_copy_id", "recorded_on", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    snapshot_id: int | None = Field(default=None, foreign_key="p68_market_price_snapshot.id", nullable=True)
    recorded_on: date = Field(sa_column=Column(Date, nullable=False, index=True))
    recorded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    blended_fmv: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    raw_fmv: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    confidence: float = Field(default=0.0, nullable=False)
    liquidity_score: float = Field(default=0.0, nullable=False)
    sales_count: int = Field(default=0, nullable=False)
    price_trend_7d: str = Field(default="STABLE", max_length=16, nullable=False)
    price_trend_30d: str = Field(default="STABLE", max_length=16, nullable=False)
    price_trend_90d: str = Field(default="STABLE", max_length=16, nullable=False)
    provider_breakdown_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
