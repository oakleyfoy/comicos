from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RetailerKey = Literal["midtown"]


class RetailerAccountCreate(BaseModel):
    retailer: RetailerKey = "midtown"
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=200)
    sync_enabled: bool = False


class RetailerAccountUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=320)
    password: str | None = Field(default=None, min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=200)
    sync_enabled: bool | None = None
    status: str | None = Field(default=None, max_length=32)


class RetailerAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer: str
    display_name: str | None = None
    masked_username: str
    credential_version: int
    status: str
    sync_enabled: bool
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class RetailerSyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_account_id: int
    retailer: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    orders_seen: int
    orders_imported: int
    items_seen: int
    items_imported: int
    items_updated: int
    errors_count: int
    summary_json: dict = Field(default_factory=dict)
    error_message: str | None = None


class RetailerOrderItemSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_item_id: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    title: str
    publisher: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    quantity: int
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    item_status: str | None = None
    shipped_qty: int | None = None
    backordered_qty: int | None = None
    unavailable_qty: int | None = None
    returned_qty: int | None = None
    release_date: date | None = None
    updated_at: datetime


class RetailerOrderSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retailer_account_id: int
    retailer: str
    retailer_order_number: str
    order_date: date | None = None
    order_status: str | None = None
    order_total: Decimal | None = None
    source_url: str | None = None
    updated_at: datetime
    items: list[RetailerOrderItemSnapshotRead] = Field(default_factory=list)


class RetailerAccountSyncRequest(BaseModel):
    limit_orders: int = Field(default=25, ge=1, le=100)


class RetailerLocalSyncStartRequest(BaseModel):
    limit_orders: int = Field(default=25, ge=1, le=100)


class RetailerLocalSyncDetailPageCapture(BaseModel):
    detail_url: str = Field(min_length=1, max_length=2048)
    html: str = Field(min_length=1)
    retailer_order_number: str | None = Field(default=None, max_length=128)
    fallback_order_number: str | None = Field(default=None, max_length=128)


class RetailerLocalSyncCompleteRequest(BaseModel):
    helper_token: str = Field(min_length=1, max_length=512)
    history_html: str = Field(min_length=1)
    detail_pages: list[RetailerLocalSyncDetailPageCapture] = Field(default_factory=list)


class RetailerAccountTestResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead


class RetailerLocalSyncStartResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead
    helper_token: str
    helper_token_expires_at: datetime
    capture_url: str
    helper_mode: str = "bookmarklet"


class RetailerAccountSyncResponse(BaseModel):
    account: RetailerAccountRead
    run: RetailerSyncRunRead
    orders: list[RetailerOrderSnapshotRead] = Field(default_factory=list)


class RetailerAccountsListResponse(BaseModel):
    items: list[RetailerAccountRead] = Field(default_factory=list)


class RetailerSyncRunListResponse(BaseModel):
    items: list[RetailerSyncRunRead] = Field(default_factory=list)


class RetailerOrderListResponse(BaseModel):
    items: list[RetailerOrderSnapshotRead] = Field(default_factory=list)
