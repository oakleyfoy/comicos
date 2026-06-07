"""P88-03 marketplace saved searches and alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceSavedSearch(SQLModel, table=True):
    __tablename__ = "p88_marketplace_saved_search"
    __table_args__ = (SAIndex("ix_p88_mkt_saved_search_owner_active", "owner_user_id", "is_active", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    name: str = Field(default="", max_length=200, nullable=False)
    marketplace: str = Field(default="EBAY", max_length=32, nullable=False, index=True)
    query: str = Field(default="", max_length=512, nullable=False)
    series: str = Field(default="", max_length=200, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    publisher: str = Field(default="", max_length=160, nullable=False)
    variant: str = Field(default="", max_length=200, nullable=False)
    max_price: float | None = Field(default=None, nullable=True)
    min_discount_to_fmv: float | None = Field(default=None, nullable=True)
    condition_filter: str = Field(default="", max_length=128, nullable=False)
    is_active: bool = Field(default=True, nullable=False, index=True)
    last_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_success_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_error: str = Field(default="", max_length=512, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceAlert(SQLModel, table=True):
    __tablename__ = "p88_marketplace_alert"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "listing_id",
            "alert_type",
            "dedupe_key",
            name="uq_p88_mkt_alert_dedupe",
        ),
        SAIndex("ix_p88_mkt_alert_owner_status", "owner_user_id", "status", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    saved_search_id: int | None = Field(
        default=None,
        foreign_key="p88_marketplace_saved_search.id",
        nullable=True,
        index=True,
    )
    opportunity_id: int | None = Field(
        default=None,
        foreign_key="p82_marketplace_acquisition_opportunity.id",
        nullable=True,
        index=True,
    )
    listing_id: int | None = Field(
        default=None,
        foreign_key="p88_marketplace_listing.id",
        nullable=True,
        index=True,
    )
    alert_type: str = Field(max_length=32, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    severity: str = Field(default="MEDIUM", max_length=16, nullable=False, index=True)
    status: str = Field(default="NEW", max_length=16, nullable=False, index=True)
    dedupe_key: str = Field(default="", max_length=128, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceMonitoringRun(SQLModel, table=True):
    __tablename__ = "p88_marketplace_monitoring_run"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    saved_search_id: int | None = Field(
        default=None,
        foreign_key="p88_marketplace_saved_search.id",
        nullable=True,
        index=True,
    )
    searches_run: int = Field(default=0, nullable=False)
    listings_found: int = Field(default=0, nullable=False)
    new_listings: int = Field(default=0, nullable=False)
    price_drops: int = Field(default=0, nullable=False)
    below_fmv_alerts: int = Field(default=0, nullable=False)
    watchlist_matches: int = Field(default=0, nullable=False)
    errors_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
