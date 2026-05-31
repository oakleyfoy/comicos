from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceInventoryReservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int = Field(gt=0)
    inventory_copy_id: int | None = Field(default=None, gt=0)
    reservation_type: str = Field(min_length=1, max_length=40)
    quantity_reserved: int = Field(ge=1, le=9999)
    source: str = Field(min_length=1, max_length=80)
    expires_at: datetime | None = None


class MarketplaceOrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int | None = Field(default=None, gt=0)
    inventory_copy_id: int | None = Field(default=None, gt=0)
    external_item_id: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    quantity: int = Field(ge=1, le=9999)
    unit_price: Decimal = Field(ge=0)


class MarketplaceOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: int | None = Field(default=None, gt=0)
    marketplace_account_id: int | None = Field(default=None, gt=0)
    external_order_id: str | None = Field(default=None, max_length=200)
    buyer_name: str | None = Field(default=None, max_length=200)
    buyer_email: str | None = Field(default=None, max_length=320)
    shipping_amount: Decimal = Field(default=0, ge=0)
    tax_amount: Decimal = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    ordered_at: datetime | None = None
    items: list[MarketplaceOrderItemCreate] = Field(min_length=1)


class MarketplaceInventorySyncPlanGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_ids: list[int] = Field(default_factory=list)
    marketplace_ids: list[int] = Field(default_factory=list)


class MarketplaceInventoryReservationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    listing_id: int
    inventory_copy_id: int | None = None
    reservation_uuid: str
    reservation_type: str
    quantity_reserved: int
    status: str
    source: str
    expires_at: datetime | None = None
    created_at: datetime
    released_at: datetime | None = None


class MarketplaceInventoryAvailabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    listing_id: int
    inventory_copy_id: int | None = None
    total_quantity: int
    reserved_quantity: int
    available_quantity: int
    sold_quantity: int
    calculated_at: datetime


class MarketplaceOrderItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    order_id: int
    listing_id: int | None = None
    inventory_copy_id: int | None = None
    external_item_id: str | None = None
    title: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    item_status: str
    created_at: datetime
    updated_at: datetime


class MarketplaceOrderEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    order_id: int
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceOrderRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    marketplace_id: int | None = None
    marketplace_account_id: int | None = None
    order_uuid: str
    external_order_id: str | None = None
    order_status: str
    buyer_name: str | None = None
    buyer_email: str | None = None
    subtotal_amount: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    ordered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MarketplaceOrderDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: MarketplaceOrderRead
    items: list[MarketplaceOrderItemRead] = Field(default_factory=list)
    events: list[MarketplaceOrderEventRead] = Field(default_factory=list)


class MarketplaceInventorySyncPlanItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    plan_id: int
    listing_id: int
    marketplace_id: int | None = None
    marketplace_account_id: int | None = None
    current_available_quantity: int
    target_available_quantity: int
    action_type: str
    reason: str
    created_at: datetime


class MarketplaceInventorySyncPlanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    plan_uuid: str
    plan_type: str
    status: str
    generated_at: datetime
    created_at: datetime


class MarketplaceInventorySyncPlanDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: MarketplaceInventorySyncPlanRead
    items: list[MarketplaceInventorySyncPlanItemRead] = Field(default_factory=list)


class MarketplaceInventoryReservationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventoryReservationRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceInventoryAvailabilityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventoryAvailabilityRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceOrderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOrderRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceInventorySyncPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventorySyncPlanRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
