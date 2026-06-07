"""P90-01 unified collector alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P90_ALERT_TYPES = (
    "BUY_OPPORTUNITY",
    "SELL_OPPORTUNITY",
    "GRADE_OPPORTUNITY",
    "COLLECTION_GAP",
    "PRICE_DROP",
    "RELEASE_ALERT",
    "WATCHLIST_MATCH",
    "PORTFOLIO_ACTION",
)
P90_ALERT_SEVERITY = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
P90_ALERT_STATUS = ("NEW", "ACKNOWLEDGED", "DISMISSED", "COMPLETED")


class P90CollectorAlert(SQLModel, table=True):
    __tablename__ = "p90_collector_alert"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "alert_type",
            "entity_type",
            "entity_id",
            name="uq_p90_collector_alert_entity",
        ),
        SAIndex("ix_p90_alert_owner_status_pri", "owner_user_id", "status", "priority_score"),
        SAIndex("ix_p90_alert_owner_type", "owner_user_id", "alert_type", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    alert_type: str = Field(max_length=32, nullable=False, index=True)
    severity: str = Field(default="MEDIUM", max_length=16, nullable=False, index=True)
    priority_score: float = Field(default=0.0, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    source_system: str = Field(default="", max_length=64, nullable=False)
    entity_type: str = Field(default="", max_length=64, nullable=False)
    entity_id: int = Field(default=0, nullable=False, index=True)
    status: str = Field(default="NEW", max_length=16, nullable=False, index=True)
    confidence: str = Field(default="MEDIUM", max_length=8, nullable=False)
    reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    action_route: str = Field(default="", max_length=512, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    dismissed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class P90AutomationRun(SQLModel, table=True):
    __tablename__ = "p90_automation_run"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="SUCCESS", max_length=16, nullable=False, index=True)
    alerts_created: int = Field(default=0, nullable=False)
    alerts_updated: int = Field(default=0, nullable=False)
    alerts_dismissed: int = Field(default=0, nullable=False)
    errors: str = Field(default="", sa_column=Column(Text, nullable=False))
