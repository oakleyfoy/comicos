"""P62-03/04/05 Collector Intelligence Suite models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

P62_COLLECTOR_SOURCE_VERSION = "P62-03-05"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


FOC_STATUS_NEW = "NEW"
FOC_STATUS_REVIEWED = "REVIEWED"
FOC_STATUS_ORDERED = "ORDERED"
FOC_STATUS_DISMISSED = "DISMISSED"

FORECAST_CONF_HIGH = "HIGH"
FORECAST_CONF_MEDIUM = "MEDIUM"
FORECAST_CONF_LOW = "LOW"

AUTO_WL_TYPES = (
    "AUTO_DEMAND_RISING",
    "AUTO_SPEC_TOP",
    "AUTO_FOC_THIS_WEEK",
    "AUTO_FOC_NEXT_30_DAYS",
    "AUTO_BATMAN",
    "AUTO_SPIDER_MAN",
    "AUTO_IMAGE",
    "AUTO_INDIE_BREAKOUT",
    "AUTO_CREATOR_FOLLOWING",
    "AUTO_PUBLISHER_FOLLOWING",
)


class FOCAlertSnapshot(SQLModel, table=True):
    __tablename__ = "foc_alert_snapshot"
    __table_args__ = (SAIndex("ix_foc_alert_snapshot_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P62_COLLECTOR_SOURCE_VERSION, max_length=32, nullable=False)


class FOCAlertItem(SQLModel, table=True):
    __tablename__ = "foc_alert_item"
    __table_args__ = (SAIndex("ix_foc_alert_item_snapshot_urgency", "snapshot_id", "urgency_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="foc_alert_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    foc_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    release_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    recommendation_score: float = Field(default=0.0, nullable=False)
    demand_score: float = Field(default=0.0, nullable=False)
    velocity_score: float = Field(default=0.0, nullable=False)
    spec_score: float = Field(default=0.0, nullable=False)
    urgency_score: float = Field(default=0.0, nullable=False, index=True)
    alert_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    suggested_quantity: int = Field(default=1, nullable=False)
    status: str = Field(default=FOC_STATUS_NEW, max_length=16, nullable=False, index=True)


class FuturePullForecast(SQLModel, table=True):
    __tablename__ = "future_pull_forecast"
    __table_args__ = (SAIndex("ix_future_pull_forecast_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P62_COLLECTOR_SOURCE_VERSION, max_length=32, nullable=False)


class FuturePullForecastItem(SQLModel, table=True):
    __tablename__ = "future_pull_forecast_item"
    __table_args__ = (SAIndex("ix_future_pull_forecast_item_forecast_conf", "forecast_id", "confidence", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    forecast_id: int = Field(foreign_key="future_pull_forecast.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    series_name: str = Field(default="", max_length=200, nullable=False)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    confidence: str = Field(default=FORECAST_CONF_LOW, max_length=16, nullable=False, index=True)
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))
    reasons_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class AutoWatchlist(SQLModel, table=True):
    __tablename__ = "auto_watchlist"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "watchlist_type", "generation_epoch", name="uq_auto_watchlist_owner_type_epoch"),
        SAIndex("ix_auto_watchlist_owner_type", "owner_user_id", "watchlist_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    watchlist_type: str = Field(max_length=48, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    generation_epoch: int = Field(default=1, nullable=False, index=True)
    item_count: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P62_COLLECTOR_SOURCE_VERSION, max_length=32, nullable=False)


class AutoWatchlistItem(SQLModel, table=True):
    __tablename__ = "auto_watchlist_item"
    __table_args__ = (SAIndex("ix_auto_watchlist_item_list_issue", "watchlist_id", "release_issue_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    watchlist_id: int = Field(foreign_key="auto_watchlist.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    inclusion_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
