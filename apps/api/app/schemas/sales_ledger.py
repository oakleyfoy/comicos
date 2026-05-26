"""P36-03 schemas for deterministic realized sales truth."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SaleChannel = Literal["manual", "ebay", "whatnot", "shopify", "hipcomic", "shortboxed", "convention", "private_sale"]
SaleStatus = Literal["DRAFT", "RECORDED", "VOIDED"]
SaleAdjustmentType = Literal[
    "platform_fee",
    "payment_fee",
    "shipping_cost",
    "tax_collected",
    "shipping_charged",
    "discount",
    "refund",
    "other",
]
SaleLifecycleEventType = Literal["CREATED", "RECORDED", "UPDATED", "VOIDED", "FINANCIAL_RECALCULATED"]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class SaleRecordLineItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    quantity_sold: int = Field(default=1, ge=1, le=1_000_000)
    unit_sale_amount: Decimal = Field(ge=Decimal("0"))
    line_subtotal_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    cost_basis_amount: Decimal | None = Field(default=None, ge=Decimal("0"))


class SaleFinancialAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustment_type: SaleAdjustmentType
    amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=8)
    description: str | None = Field(default=None, max_length=2000)

    _trim_currency = field_validator("currency", mode="before")(_trim)
    _trim_description = field_validator("description", mode="before")(_trim)


class SaleRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int | None = Field(default=None, ge=1)
    channel: SaleChannel
    sale_date: date
    currency: str = Field(min_length=3, max_length=8)
    buyer_reference: str | None = Field(default=None, max_length=255)
    line_items: list[SaleRecordLineItemCreate] = Field(min_length=1)
    financial_adjustments: list[SaleFinancialAdjustmentCreate] = Field(default_factory=list)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)

    _trim_currency = field_validator("currency", mode="before")(_trim)
    _trim_buyer_reference = field_validator("buyer_reference", mode="before")(_trim)
    _trim_replay_key = field_validator("replay_key", mode="before")(_trim)


class SaleRecordPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int | None = Field(default=None, ge=1)
    channel: SaleChannel | None = None
    sale_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    buyer_reference: str | None = Field(default=None, max_length=255)

    _trim_currency = field_validator("currency", mode="before")(_trim)
    _trim_buyer_reference = field_validator("buyer_reference", mode="before")(_trim)


class SaleRecordLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_record_id: int
    listing_id: int | None
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    quantity_sold: int
    unit_sale_amount: Decimal
    line_subtotal_amount: Decimal
    cost_basis_amount: Decimal | None
    realized_profit_amount: Decimal | None
    created_at: datetime


class SaleFinancialAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_record_id: int
    adjustment_type: SaleAdjustmentType
    amount: Decimal
    currency: str
    description: str | None
    created_at: datetime


class SaleLifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_record_id: int
    event_type: SaleLifecycleEventType
    prior_status: str | None
    new_status: str | None
    metadata_json: dict
    created_by_user_id: int | None
    created_at: datetime


class SaleRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    listing_id: int | None
    channel: SaleChannel
    status: SaleStatus
    sale_date: date
    buyer_reference: str | None
    currency: str
    gross_sale_amount: Decimal
    item_subtotal_amount: Decimal
    shipping_charged_amount: Decimal
    tax_collected_amount: Decimal
    platform_fee_amount: Decimal
    payment_fee_amount: Decimal
    shipping_cost_amount: Decimal
    other_cost_amount: Decimal
    net_proceeds_amount: Decimal
    acquisition_cost_basis_amount: Decimal | None
    realized_profit_amount: Decimal | None
    realized_margin_pct: Decimal | None
    replay_key: str | None
    created_at: datetime
    updated_at: datetime
    recorded_at: datetime | None
    voided_at: datetime | None
    event_count: int = 0
    line_item_count: int = 0
    adjustment_count: int = 0


class SaleRecordDetailRead(SaleRecordRead):
    line_items: list[SaleRecordLineItemRead] = Field(default_factory=list)
    financial_adjustments: list[SaleFinancialAdjustmentRead] = Field(default_factory=list)
    events: list[SaleLifecycleEventRead] = Field(default_factory=list)


class SaleRecordListResponse(BaseModel):
    items: list[SaleRecordRead]
    total_items: int
    limit: int
    offset: int


class SaleLifecycleEventListResponse(BaseModel):
    items: list[SaleLifecycleEventRead]
    total_items: int
    limit: int
    offset: int


class SaleFinancialAdjustmentListResponse(BaseModel):
    items: list[SaleFinancialAdjustmentRead]
    total_items: int
    limit: int
    offset: int


class SaleChannelCountRow(BaseModel):
    channel: SaleChannel
    count: int


class SalesDashboardSummary(BaseModel):
    completed_sale_count: int
    gross_sales_total: Decimal
    net_proceeds_total: Decimal
    realized_profit_total: Decimal
    recent_sales: list[SaleRecordRead]
    sales_count_by_channel: list[SaleChannelCountRow]
