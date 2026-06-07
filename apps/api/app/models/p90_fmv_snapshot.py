"""P90-02 FMV Intelligence V2 snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P90_FMV_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
P90_FMV_TREND = ("UP", "FLAT", "DOWN")
P90_FMV_SOURCE = ("MARKETPLACE", "HYBRID", "LEGACY")


class P90FmvSnapshot(SQLModel, table=True):
    __tablename__ = "p90_fmv_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "series",
            "issue_number",
            "variant",
            "snapshot_date",
            name="uq_p90_fmv_snap_day",
        ),
        SAIndex("ix_p90_fmv_owner_date", "owner_user_id", "snapshot_date"),
        SAIndex("ix_p90_fmv_owner_conf", "owner_user_id", "valuation_confidence"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    series: str = Field(default="", max_length=200, nullable=False, index=True)
    issue_number: str = Field(default="", max_length=32, nullable=False, index=True)
    variant: str = Field(default="", max_length=200, nullable=False)
    quick_sale_value: float = Field(default=0.0, nullable=False)
    market_value: float = Field(default=0.0, nullable=False)
    premium_value: float = Field(default=0.0, nullable=False)
    valuation_confidence: str = Field(default="LOW", max_length=8, nullable=False, index=True)
    trend_direction: str = Field(default="FLAT", max_length=8, nullable=False)
    trend_score: float = Field(default=0.0, nullable=False)
    sales_velocity: str = Field(default="NORMAL", max_length=16, nullable=False)
    listing_count: int = Field(default=0, nullable=False)
    marketplace_count: int = Field(default=0, nullable=False)
    valuation_source: str = Field(default="LEGACY", max_length=16, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
