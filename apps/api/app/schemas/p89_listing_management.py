"""P89-04 Listing Management API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

P89ManagedListingStatus = Literal["DRAFT", "ACTIVE", "SOLD", "EXPIRED", "ARCHIVED", "CANCELLED"]
P89ManagedMarketplace = Literal["EBAY", "WHATNOT", "MYCOMICSHOP", "OTHER"]


class P89ManagedListingProfitRead(BaseModel):
    gross_sale: float
    total_costs: float
    net_profit: float | None = None
    profit_margin: float | None = None
    cost_basis: float | None = None
    cost_basis_known: bool = False


class P89ManagedListingStatusEventRead(BaseModel):
    status: str
    at: str


class P89ManagedListingCreate(BaseModel):
    inventory_copy_id: int | None = None
    listing_draft_id: int | None = None
    marketplace: P89ManagedMarketplace = "EBAY"
    title: str = ""
    asking_price: float | None = None
    shipping_price: float | None = None
    minimum_price: float | None = None
    listing_url: str = ""
    external_listing_id: str = ""
    notes: str = ""


class P89ManagedListingUpdate(BaseModel):
    listing_url: str | None = None
    external_listing_id: str | None = None
    asking_price: float | None = None
    shipping_price: float | None = None
    minimum_price: float | None = None
    notes: str | None = None
    title: str | None = None
    marketplace: P89ManagedMarketplace | None = None


class P89ManagedListingMarkSold(BaseModel):
    sale_price: float = Field(ge=0)
    shipping_charged: float | None = Field(default=None, ge=0)
    marketplace_fees: float | None = Field(default=None, ge=0)
    shipping_cost: float | None = Field(default=None, ge=0)
    sold_at: datetime | None = None


class P89ManagedListingRead(BaseModel):
    id: int
    owner_user_id: int
    inventory_copy_id: int
    listing_draft_id: int | None = None
    marketplace: P89ManagedMarketplace
    listing_url: str
    external_listing_id: str
    title: str
    comic_title: str = ""
    asking_price: float | None = None
    shipping_price: float | None = None
    minimum_price: float | None = None
    status: P89ManagedListingStatus
    listed_at: datetime | None = None
    sold_at: datetime | None = None
    expired_at: datetime | None = None
    archived_at: datetime | None = None
    sale_price: float | None = None
    shipping_charged: float | None = None
    marketplace_fees: float | None = None
    shipping_cost: float | None = None
    net_profit: float | None = None
    notes: str = ""
    profit: P89ManagedListingProfitRead | None = None
    status_history: list[P89ManagedListingStatusEventRead] = Field(default_factory=list)
    inventory_auto_updated: bool = False
    created_at: datetime
    updated_at: datetime


class P89ManagedListingListRead(BaseModel):
    items: list[P89ManagedListingRead]
    total_items: int
    limit: int
    offset: int


class P89ManagedListingPortfolioSummaryRead(BaseModel):
    realized_sales_total: float
    total_net_profit: float
    active_listing_value: float
    sold_this_month_count: int
    sold_this_month_net_profit: float
    active_listings_count: int


class P89ManagedListingInventorySoldRead(BaseModel):
    inventory_copy_id: int
    order_status: str
