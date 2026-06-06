"""P73-02 recommendation profitability snapshot aggregates."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Numeric
from sqlmodel import Field, SQLModel

from app.models.recommendation_performance_snapshot import P73_ANALYTICS_SOURCE_VERSION


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationProfitabilitySnapshot(SQLModel, table=True):
    __tablename__ = "p73_recommendation_profitability_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_profit_snap_owner", "owner_user_id", "performance_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    performance_snapshot_id: int = Field(
        foreign_key="p73_recommendation_performance_snapshot.id",
        nullable=False,
        index=True,
    )
    expected_profit: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    actual_profit: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    expected_roi_pct: float = Field(default=0.0, nullable=False)
    actual_roi_pct: float = Field(default=0.0, nullable=False)
    breakdown_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P73_ANALYTICS_SOURCE_VERSION, max_length=32, nullable=False)
