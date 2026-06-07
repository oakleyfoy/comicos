"""P88-02 live marketplace listings."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P88MarketplaceListing(SQLModel, table=True):
    __tablename__ = "p88_marketplace_listing"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "marketplace", "item_id", name="uq_p88_mkt_listing_item"),
        SAIndex("ix_p88_mkt_listing_opp", "opportunity_id", "is_active"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    opportunity_id: int | None = Field(
        default=None,
        foreign_key="p82_marketplace_acquisition_opportunity.id",
        nullable=True,
        index=True,
    )
    marketplace: str = Field(default="EBAY", max_length=32, nullable=False, index=True)
    item_id: str = Field(max_length=64, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    listing_url: str = Field(default="", max_length=2048, nullable=False)
    image_url: str = Field(default="", max_length=2048, nullable=False)
    price: float = Field(default=0.0, nullable=False)
    previous_price: float | None = Field(default=None, nullable=True)
    shipping_cost: float = Field(default=0.0, nullable=False)
    condition: str = Field(default="", max_length=128, nullable=False)
    seller_name: str = Field(default="", max_length=128, nullable=False)
    listing_type: str = Field(default="", max_length=64, nullable=False)
    end_time: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    is_active: bool = Field(default=True, nullable=False, index=True)
    health_status: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    marketplace_name: str = Field(default="", max_length=64, nullable=False)
    availability_status: str = Field(default="UNKNOWN", max_length=16, nullable=False, index=True)
    listing_confidence: str = Field(default="MEDIUM", max_length=8, nullable=False)
    currency: str = Field(default="USD", max_length=8, nullable=False)
    price_last_changed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_verified_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_price_drop_alert_price: float | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceSearchRun(SQLModel, table=True):
    __tablename__ = "p88_marketplace_search_run"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    searches_run: int = Field(default=0, nullable=False)
    listings_found: int = Field(default=0, nullable=False)
    new_listings: int = Field(default=0, nullable=False)
    updated_listings: int = Field(default=0, nullable=False)
    failed_searches: int = Field(default=0, nullable=False)
    errors_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
