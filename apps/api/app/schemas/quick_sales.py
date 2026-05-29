from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class QuickSalePermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class QuickSaleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    convention_session_id: int | None
    mobile_device_id: int | None
    sale_identifier: str
    sale_status: str
    buyer_label: str | None
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str
    sale_source: str
    created_by_user_id: int
    created_at: datetime
    completed_at: datetime | None
    voided_at: datetime | None


class QuickSaleLineItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    quick_sale_id: int
    inventory_item_id: int | None
    offline_inventory_record_id: int | None
    marketplace_listing_draft_id: int | None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    line_status: str
    created_at: datetime


class QuickSalePaymentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    quick_sale_id: int
    payment_method: str
    payment_status: str
    amount: Decimal
    currency: str
    payment_reference: str | None
    created_at: datetime


class QuickSaleEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    quick_sale_id: int | None
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class QuickSaleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_identifier: str = Field(min_length=1, max_length=128)
    convention_session_id: int | None = None
    mobile_device_id: int | None = None
    buyer_label: str | None = Field(default=None, max_length=200)
    currency: str = Field(default="USD", min_length=1, max_length=8)
    sale_source: str = Field(min_length=1, max_length=24)


class QuickSaleLineItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int | None = None
    offline_inventory_record_id: int | None = None
    marketplace_listing_draft_id: int | None = None
    quantity: int = Field(ge=1)
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.00")


class QuickSaleLineItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_status: str = Field(min_length=1, max_length=24)


class QuickSalePaymentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: str = Field(min_length=1, max_length=32)
    amount: Decimal
    currency: str = Field(default="USD", min_length=1, max_length=8)
    payment_reference: str | None = Field(default=None, max_length=255)


class QuickSaleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: QuickSalePermissionResponse
    items: list[QuickSaleResponse]
    total_items: int
    limit: int
    offset: int


class QuickSaleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale: QuickSaleResponse
    line_items: list[QuickSaleLineItemResponse]
    payments: list[QuickSalePaymentResponse]
    events: list[QuickSaleEventResponse]
