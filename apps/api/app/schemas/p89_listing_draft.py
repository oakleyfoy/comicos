"""P89-03 Listing Draft API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

P89DraftStatus = Literal["DRAFT", "REVIEWED", "ARCHIVED"]
P89DraftMarketplace = Literal["EBAY", "WHATNOT", "MYCOMICSHOP", "OTHER"]


class P89ListingDraftCreate(BaseModel):
    inventory_copy_id: int | None = None
    marketplace: P89DraftMarketplace = "EBAY"
    sell_candidate_id: int | None = None
    market_price_snapshot_id: int | None = None


class P89ListingDraftUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    condition_notes: str | None = None
    shipping_notes: str | None = None
    suggested_price: float | None = None
    minimum_price: float | None = None
    premium_price: float | None = None
    status: P89DraftStatus | None = None


class P89ListingDraftRead(BaseModel):
    id: int
    owner_user_id: int
    inventory_copy_id: int
    sell_candidate_id: int | None = None
    market_price_snapshot_id: int | None = None
    marketplace: P89DraftMarketplace
    title: str
    description: str
    condition_notes: str
    shipping_notes: str
    suggested_price: float | None = None
    minimum_price: float | None = None
    premium_price: float | None = None
    status: P89DraftStatus
    comic_title: str = ""
    pricing_unavailable: bool = False
    full_listing_text: str = ""
    created_at: datetime
    updated_at: datetime


class P89ListingDraftListRead(BaseModel):
    items: list[P89ListingDraftRead]
    total_items: int
    limit: int
    offset: int
