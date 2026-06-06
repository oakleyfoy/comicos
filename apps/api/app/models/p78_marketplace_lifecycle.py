"""P78-02 listing lifecycle, reservations, and sales."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P78_LIFECYCLE_STATUSES = (
    "CANDIDATE",
    "DRAFT",
    "READY",
    "LISTED",
    "SOLD",
    "SHIPPED",
    "COMPLETED",
)
P78_SYNC_STATES = ("ACTIVE", "SOLD", "ENDED", "CANCELLED")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P78Listing(SQLModel, table=True):
    __tablename__ = "p78_listing"
    __table_args__ = (
        SAIndex("ix_p78_listing_owner_lifecycle", "owner_user_id", "lifecycle_status", "updated_at", "id"),
        SAIndex("ix_p78_listing_owner_draft", "owner_user_id", "listing_draft_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_draft_id: int = Field(foreign_key="p78_listing_draft.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    lifecycle_status: str = Field(default="LISTED", max_length=16, nullable=False, index=True)
    sync_state: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    marketplace: str = Field(default="EBAY", max_length=24, nullable=False)
    external_listing_id: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    listing_url: str | None = Field(default=None, max_length=512, nullable=True)
    title: str = Field(default="", max_length=512, nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    condition_label: str = Field(default="NM", max_length=32, nullable=False)
    asking_price: float = Field(default=0.0, nullable=False)
    sold_price: float | None = Field(default=None, nullable=True)
    quantity_listed: int = Field(default=1, nullable=False)
    quantity_reserved: int = Field(default=0, nullable=False)
    fees: float = Field(default=0.0, nullable=False)
    shipping_cost: float = Field(default=0.0, nullable=False)
    export_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    listed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    sold_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P78InventoryReservation(SQLModel, table=True):
    __tablename__ = "p78_inventory_reservation"
    __table_args__ = (SAIndex("ix_p78_reservation_owner_listing", "owner_user_id", "listing_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="p78_listing.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    quantity: int = Field(default=1, nullable=False)
    active: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    released_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class P78SaleRecord(SQLModel, table=True):
    __tablename__ = "p78_sale_record"
    __table_args__ = (SAIndex("ix_p78_sale_owner_sold", "owner_user_id", "sold_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="p78_listing.id", nullable=False, index=True)
    marketplace: str = Field(default="EBAY", max_length=24, nullable=False)
    sale_price: float = Field(default=0.0, nullable=False)
    fees: float = Field(default=0.0, nullable=False)
    shipping_cost: float = Field(default=0.0, nullable=False)
    cost_basis: float = Field(default=0.0, nullable=False)
    profit: float = Field(default=0.0, nullable=False)
    roi_pct: float = Field(default=0.0, nullable=False)
    quantity_sold: int = Field(default=1, nullable=False)
    sold_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    p73_outcome_id: int | None = Field(default=None, foreign_key="p73_recommendation_outcome.id", nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P78SellingAnalyticsSnapshot(SQLModel, table=True):
    __tablename__ = "p78_selling_analytics_snapshot"
    __table_args__ = (SAIndex("ix_p78_sell_analytics_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
