from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceOrderLineItemImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int | None = Field(default=None, gt=0)
    marketplace_listing_identifier: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1, le=9999)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)


class MarketplaceTransactionImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_type: str = Field(min_length=1, max_length=32)
    transaction_status: str = Field(default="completed", min_length=4, max_length=24)
    gross_amount: Decimal = Field(ge=0)
    fee_amount: Decimal = Field(ge=0)
    net_amount: Decimal = Field(ge=0)
    transaction_currency: str = Field(default="USD", min_length=3, max_length=8)
    transaction_reference: str = Field(min_length=1, max_length=255)


class MarketplaceOrderImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    marketplace_order_identifier: str = Field(min_length=1, max_length=255)
    marketplace_type: str | None = Field(default=None, min_length=2, max_length=32)
    order_status: str = Field(default="imported", min_length=4, max_length=24)
    buyer_identifier: str | None = Field(default=None, max_length=255)
    order_total: Decimal = Field(ge=0)
    order_currency: str = Field(default="USD", min_length=3, max_length=8)
    ordered_at: datetime | None = None
    line_items: list[MarketplaceOrderLineItemImportRequest] = Field(default_factory=list)
    transactions: list[MarketplaceTransactionImportRequest] = Field(default_factory=list)


class MarketplaceOrderReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int | None = Field(default=None, gt=0)


class MarketplaceOrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    marketplace_order_identifier: str
    marketplace_type: str
    order_status: str
    buyer_identifier: str | None = None
    order_total: Decimal
    order_currency: str
    ordered_at: datetime
    imported_at: datetime
    created_at: datetime


class MarketplaceOrderLineItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_order_id: int
    inventory_item_id: int | None = None
    marketplace_listing_identifier: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime


class MarketplaceTransactionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_order_id: int
    transaction_type: str
    transaction_status: str
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    transaction_currency: str
    transaction_reference: str
    created_at: datetime


class MarketplaceOrderEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_order_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceOrderPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceOrderImportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int
    duplicate_detected: bool
    imported_line_items: int
    imported_transactions: int
    order_total: Decimal
    order_currency: str


class MarketplaceOrderDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: MarketplaceOrderResponse
    line_items: list[MarketplaceOrderLineItemResponse] = Field(default_factory=list)
    transactions: list[MarketplaceTransactionResponse] = Field(default_factory=list)
    events: list[MarketplaceOrderEventResponse] = Field(default_factory=list)
    import_summary: MarketplaceOrderImportSummaryResponse
    permissions: MarketplaceOrderPermissionResponse


class MarketplaceOrderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOrderResponse] = Field(default_factory=list)
    permissions: MarketplaceOrderPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceTransactionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceTransactionResponse] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceTransactionMismatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mismatch_code: str
    message: str
    order_id: int
    transaction_references: list[str] = Field(default_factory=list)


class MarketplaceTransactionReconciliationReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mismatches: list[MarketplaceTransactionMismatchResponse] = Field(default_factory=list)
    total_orders: int
    total_transactions: int
