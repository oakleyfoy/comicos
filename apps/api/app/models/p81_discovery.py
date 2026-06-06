"""P81-01 future release discovery registry and snapshots."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

P81_OPPORTUNITY_TYPES = (
    "NEW_SERIES",
    "NEW_1",
    "MILESTONE",
    "ANNIVERSARY",
    "CREATOR_PROJECT",
    "VARIANT_EXPANSION",
)
P81_REGISTRY_STATUSES = ("DISCOVERED", "QUALIFIED", "SCORED", "PUBLISHED")
P81_SCORE_CATEGORIES = ("MUST_WATCH", "HIGH_OPPORTUNITY", "WATCH", "LOW_PRIORITY")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P81DiscoveryOpportunity(SQLModel, table=True):
    __tablename__ = "p81_discovery_opportunity"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "opportunity_key", name="uq_p81_discovery_opportunity_key"),
        SAIndex("ix_p81_discovery_owner_score", "owner_user_id", "discovery_score", "id"),
        SAIndex("ix_p81_discovery_owner_category", "owner_user_id", "score_category", "updated_at", "id"),
        SAIndex("ix_p81_discovery_owner_type", "owner_user_id", "opportunity_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    opportunity_key: str = Field(max_length=320, nullable=False, index=True)
    opportunity_type: str = Field(max_length=32, nullable=False, index=True)
    registry_status: str = Field(default="DISCOVERED", max_length=16, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=160, nullable=False, index=True)
    series_name: str = Field(default="", max_length=200, nullable=False, index=True)
    issue_number: str = Field(default="", max_length=24, nullable=False)
    variant_label: str = Field(default="", max_length=200, nullable=False)
    discovery_date: date = Field(default_factory=date.today, sa_column=Column(Date, nullable=False))
    release_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    creator_metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    signals_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    discovery_score: float = Field(default=0.0, nullable=False, index=True)
    score_category: str = Field(default="LOW_PRIORITY", max_length=24, nullable=False, index=True)
    source_type: str = Field(default="RELEASE", max_length=32, nullable=False, index=True)
    source_ref_id: int | None = Field(default=None, nullable=True, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    external_catalog_issue_id: int | None = Field(
        default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81DiscoverySnapshot(SQLModel, table=True):
    __tablename__ = "p81_discovery_snapshot"
    __table_args__ = (SAIndex("ix_p81_discovery_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


P81_WATCHLIST_TYPES = ("PUBLISHER", "CHARACTER", "CREATOR", "SERIES")
P81_ALERT_PRIORITIES = ("CRITICAL", "HIGH", "NORMAL", "LOW")
P81_ALERT_STATUSES = ("ACTIVE", "READ", "DISMISSED")
P81_PIPELINE_STATUSES = ("DISCOVERED", "WATCHING", "ANNOUNCED", "FOC", "PURCHASED")
P81_PERSONALIZED_CATEGORIES = ("MUST_BUY", "HIGH_PRIORITY", "WATCH", "LOW_PRIORITY", "IGNORE")


class P81DiscoveryWatchlist(SQLModel, table=True):
    __tablename__ = "p81_discovery_watchlist"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "watchlist_type", "label", name="uq_p81_discovery_watchlist_label"),
        SAIndex("ix_p81_discovery_watchlist_owner", "owner_user_id", "active", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    watchlist_type: str = Field(max_length=16, nullable=False, index=True)
    label: str = Field(max_length=200, nullable=False)
    auto_managed: bool = Field(default=False, nullable=False, index=True)
    active: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81DiscoveryAlert(SQLModel, table=True):
    __tablename__ = "p81_discovery_alert"
    __table_args__ = (
        SAIndex("ix_p81_discovery_alert_owner_status", "owner_user_id", "status", "priority", "id"),
        SAIndex("ix_p81_discovery_alert_owner_opp", "owner_user_id", "opportunity_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    opportunity_id: int = Field(foreign_key="p81_discovery_opportunity.id", nullable=False, index=True)
    alert_type: str = Field(max_length=32, nullable=False, index=True)
    priority: str = Field(max_length=16, nullable=False, index=True)
    title: str = Field(max_length=512, nullable=False)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    status: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    personalized_score: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P81FuturePullListItem(SQLModel, table=True):
    __tablename__ = "p81_future_pull_list_item"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "opportunity_id", name="uq_p81_future_pull_opportunity"),
        SAIndex("ix_p81_future_pull_owner_pipeline", "owner_user_id", "pipeline_status", "personalized_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    opportunity_id: int = Field(foreign_key="p81_discovery_opportunity.id", nullable=False, index=True)
    title: str = Field(max_length=512, nullable=False)
    series_name: str = Field(default="", max_length=200, nullable=False)
    issue_number: str = Field(default="", max_length=24, nullable=False)
    pipeline_status: str = Field(default="DISCOVERED", max_length=16, nullable=False, index=True)
    watch_level: str = Field(default="NORMAL", max_length=16, nullable=False)
    recommendation_action: str = Field(default="WATCH", max_length=16, nullable=False)
    recommendation_quantity: int = Field(default=0, nullable=False)
    personalized_score: float = Field(default=0.0, nullable=False, index=True)
    priority_category: str = Field(default="WATCH", max_length=24, nullable=False, index=True)
    release_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    foc_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
