"""P89-02 Market Pricing Intelligence snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P89_PRICING_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
P89_SALES_VELOCITY = ("VERY_FAST", "FAST", "NORMAL", "SLOW", "VERY_SLOW")
P89_TREND = ("UP", "FLAT", "DOWN")


class P89MarketPriceSnapshot(SQLModel, table=True):
    __tablename__ = "p89_market_price_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "series",
            "issue_number",
            "variant",
            "snapshot_date",
            name="uq_p89_mkt_price_snap_day",
        ),
        SAIndex("ix_p89_mkt_price_owner_date", "owner_user_id", "snapshot_date"),
        SAIndex("ix_p89_mkt_price_owner_conf", "owner_user_id", "pricing_confidence"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    series: str = Field(default="", max_length=200, nullable=False, index=True)
    issue_number: str = Field(default="", max_length=32, nullable=False, index=True)
    variant: str = Field(default="", max_length=200, nullable=False)
    quick_sale_price: float = Field(default=0.0, nullable=False)
    market_price: float = Field(default=0.0, nullable=False)
    premium_price: float = Field(default=0.0, nullable=False)
    pricing_confidence: str = Field(default="LOW", max_length=8, nullable=False, index=True)
    sales_velocity: str = Field(default="NORMAL", max_length=16, nullable=False)
    listing_count: int = Field(default=0, nullable=False)
    sold_count: int = Field(default=0, nullable=False)
    price_low: float = Field(default=0.0, nullable=False)
    price_high: float = Field(default=0.0, nullable=False)
    price_average: float = Field(default=0.0, nullable=False)
    trend_direction: str = Field(default="FLAT", max_length=8, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
