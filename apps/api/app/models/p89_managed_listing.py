"""P89-04 managed listing lifecycle (no external posting)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P89_MANAGED_LISTING_STATUSES = ("DRAFT", "ACTIVE", "SOLD", "EXPIRED", "ARCHIVED", "CANCELLED")
P89_MANAGED_MARKETPLACES = ("EBAY", "WHATNOT", "MYCOMICSHOP", "OTHER")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P89ManagedListing(SQLModel, table=True):
    __tablename__ = "p89_managed_listing"
    __table_args__ = (
        SAIndex("ix_p89_mlist_owner_status", "owner_user_id", "status"),
        SAIndex("ix_p89_mlist_owner_copy", "owner_user_id", "inventory_copy_id"),
        SAIndex("ix_p89_mlist_owner_listed", "owner_user_id", "listed_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    listing_draft_id: int | None = Field(default=None, foreign_key="p89_listing_draft.id", nullable=True, index=True)

    marketplace: str = Field(default="EBAY", max_length=16, nullable=False, index=True)
    listing_url: str = Field(default="", max_length=2048, nullable=False)
    external_listing_id: str = Field(default="", max_length=128, nullable=False)

    title: str = Field(default="", max_length=512, nullable=False)
    asking_price: float | None = Field(default=None, nullable=True)
    shipping_price: float | None = Field(default=None, nullable=True)
    minimum_price: float | None = Field(default=None, nullable=True)

    status: str = Field(default="DRAFT", max_length=16, nullable=False, index=True)

    listed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    sold_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    expired_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    sale_price: float | None = Field(default=None, nullable=True)
    shipping_charged: float | None = Field(default=None, nullable=True)
    marketplace_fees: float | None = Field(default=None, nullable=True)
    shipping_cost: float | None = Field(default=None, nullable=True)
    net_profit: float | None = Field(default=None, nullable=True)

    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    status_history_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]

    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
