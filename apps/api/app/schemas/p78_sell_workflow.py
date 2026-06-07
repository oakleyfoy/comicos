"""P78-01 sell queue and listing draft API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SellQueuePriority = Literal["HIGH", "MEDIUM", "WATCH"]
ListingDraftStatus = Literal["CANDIDATE", "DRAFT", "READY", "ARCHIVED"]


class P78SellQueueItemRead(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str = ""
    issue_number: str = ""
    priority: SellQueuePriority
    owned_copies: int = 1
    target_hold_copies: int = 2
    suggested_sell_quantity: int = 1
    fmv: float = 0.0
    cost_basis: float = 0.0
    liquidity_score: float = 0.0
    average_sale_days: float | None = None
    signals: list[str] = Field(default_factory=list)
    listing_draft_id: int | None = None
    exit_score: float | None = None


class P78SellQueueListResponse(BaseModel):
    status: str = "OK"
    message: str = ""
    items: list[P78SellQueueItemRead]
    total_items: int
    limit: int
    offset: int
    high_priority_count: int = 0
    medium_priority_count: int = 0
    watch_count: int = 0


class P78ListingPricingRead(BaseModel):
    fmv: float
    quick_sale_price: float
    market_price: float
    premium_price: float
    expected_days_to_sell: float | None = None


class P78ListingDraftRead(BaseModel):
    id: int
    owner_user_id: int
    inventory_copy_id: int | None
    status: ListingDraftStatus
    title: str
    description: str
    condition_suggested: str
    category: str
    shipping_recommendation: str
    suggested_sell_quantity: int
    fmv_at_generation: float
    quick_sale_price: float
    market_price: float
    premium_price: float
    priority: SellQueuePriority
    signals: list[str] = Field(default_factory=list)
    bundle_key: str | None = None
    created_at: datetime
    updated_at: datetime


class P78ListingDraftListResponse(BaseModel):
    items: list[P78ListingDraftRead]
    total_items: int
    limit: int
    offset: int
    status: str = "OK"
    message: str = ""


class P78ListingDraftCreate(BaseModel):
    inventory_copy_id: int = Field(gt=0)
    status: ListingDraftStatus = "DRAFT"
    suggested_sell_quantity: int | None = Field(default=None, ge=1, le=20)


class P78ListingDraftUpdate(BaseModel):
    status: ListingDraftStatus | None = None
    title: str | None = Field(default=None, max_length=512)
    description: str | None = None
    condition_suggested: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=120)
    shipping_recommendation: str | None = Field(default=None, max_length=120)
    suggested_sell_quantity: int | None = Field(default=None, ge=1, le=20)
    quick_sale_price: float | None = Field(default=None, ge=0)
    market_price: float | None = Field(default=None, ge=0)
    premium_price: float | None = Field(default=None, ge=0)


class P78SellBundleRead(BaseModel):
    bundle_key: str
    bundle_type: str
    label: str
    item_count: int
    inventory_copy_ids: list[int] = Field(default_factory=list)
    expected_bundle_fmv: float = 0.0
    suggested_list_price: float = 0.0
    signals: list[str] = Field(default_factory=list)


class P78SellBundleListResponse(BaseModel):
    items: list[P78SellBundleRead]
    total_items: int
