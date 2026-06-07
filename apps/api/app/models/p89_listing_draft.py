"""P89-03 marketplace listing drafts (copy-ready; no external posting)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P89_DRAFT_STATUS = ("DRAFT", "REVIEWED", "ARCHIVED")
P89_DRAFT_MARKETPLACES = ("EBAY", "WHATNOT", "MYCOMICSHOP", "OTHER")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P89ListingDraft(SQLModel, table=True):
    __tablename__ = "p89_listing_draft"
    __table_args__ = (
        SAIndex("ix_p89_list_draft_owner_status", "owner_user_id", "status"),
        SAIndex("ix_p89_list_draft_owner_copy", "owner_user_id", "inventory_copy_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    sell_candidate_id: int | None = Field(default=None, foreign_key="p89_sell_candidate.id", nullable=True, index=True)
    market_price_snapshot_id: int | None = Field(
        default=None,
        foreign_key="p89_market_price_snapshot.id",
        nullable=True,
        index=True,
    )
    marketplace: str = Field(default="EBAY", max_length=16, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    condition_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    shipping_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    suggested_price: float | None = Field(default=None, nullable=True)
    minimum_price: float | None = Field(default=None, nullable=True)
    premium_price: float | None = Field(default=None, nullable=True)
    status: str = Field(default="DRAFT", max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
