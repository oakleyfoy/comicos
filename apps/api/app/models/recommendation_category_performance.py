"""P73-02 per-category recommendation performance rows."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel

from app.models.recommendation_performance_snapshot import P73_ANALYTICS_SOURCE_VERSION


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P73RecommendationCategoryPerformance(SQLModel, table=True):
    __tablename__ = "p73_recommendation_category_performance"
    __table_args__ = (
        SAIndex("ix_p73_rec_cat_perf_snap", "performance_snapshot_id", "recommendation_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    performance_snapshot_id: int = Field(
        foreign_key="p73_recommendation_performance_snapshot.id",
        nullable=False,
        index=True,
    )
    recommendation_type: str = Field(max_length=32, nullable=False, index=True)
    recommendation_count: int = Field(default=0, nullable=False)
    success_rate_pct: float = Field(default=0.0, nullable=False)
    average_roi_pct: float = Field(default=0.0, nullable=False)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    source_version: str = Field(default=P73_ANALYTICS_SOURCE_VERSION, max_length=32, nullable=False)
