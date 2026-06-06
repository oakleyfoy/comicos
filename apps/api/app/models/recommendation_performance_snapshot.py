"""P73-02 recommendation performance snapshot (read-only analytics; no score changes)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel

P73_ANALYTICS_SOURCE_VERSION = "p73-02"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "p73_recommendation_performance_snapshot"
    __table_args__ = (
        SAIndex("ix_p73_rec_perf_snap_owner_gen", "owner_user_id", "generated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    recommendations_generated: int = Field(default=0, nullable=False)
    viewed: int = Field(default=0, nullable=False)
    purchased: int = Field(default=0, nullable=False)
    skipped: int = Field(default=0, nullable=False)
    held: int = Field(default=0, nullable=False)
    graded: int = Field(default=0, nullable=False)
    sold: int = Field(default=0, nullable=False)
    view_rate_pct: float = Field(default=0.0, nullable=False)
    purchase_rate_pct: float = Field(default=0.0, nullable=False)
    watchlist_rate_pct: float = Field(default=0.0, nullable=False)
    grade_rate_pct: float = Field(default=0.0, nullable=False)
    sell_rate_pct: float = Field(default=0.0, nullable=False)
    success_rate_pct: float = Field(default=0.0, nullable=False)
    failure_rate_pct: float = Field(default=0.0, nullable=False)
    average_return_pct: float = Field(default=0.0, nullable=False)
    median_return_pct: float = Field(default=0.0, nullable=False)
    win_rate_pct: float = Field(default=0.0, nullable=False)
    loss_rate_pct: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P73_ANALYTICS_SOURCE_VERSION, max_length=32, nullable=False)
