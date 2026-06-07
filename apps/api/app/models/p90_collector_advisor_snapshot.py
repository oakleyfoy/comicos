"""P90-03 Collector Advisor snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P90CollectorAdvisorSnapshot(SQLModel, table=True):
    __tablename__ = "p90_collector_advisor_snapshot"
    __table_args__ = (SAIndex("ix_p90_advisor_owner_date", "owner_user_id", "snapshot_date"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    buy_actions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    sell_actions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    grade_actions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    watch_actions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    todays_actions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    recent_activity: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    market_alerts: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    total_actions: int = Field(default=0, nullable=False)
    estimated_profit: float = Field(default=0.0, nullable=False)
    estimated_savings: float = Field(default=0.0, nullable=False)
    portfolio_score: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
