from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def validate_required_trimmed(value: str, field_name: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} is required")
    return trimmed


def normalize_optional_text_list(value: list[str] | str | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else None

    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or None


class OrderItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    publisher: str = Field(min_length=1, max_length=255)
    release_date: date | None = None
    release_year: int | None = Field(default=None, ge=0, le=9999)
    release_status: Literal["released", "not_released_yet", "unknown"] | None = None
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"] | None = None
    purchase_date: date | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    issue_number: str = Field(min_length=1, max_length=50)
    cover_name: str | None = Field(default=None, max_length=255)
    printing: str | None = Field(default=None, max_length=100)
    ratio: str | None = Field(default=None, max_length=100)
    variant_type: str | None = Field(default=None, max_length=100)
    cover_artist: str | None = Field(default=None, max_length=255)
    writers: list[str] | None = None
    artists: list[str] | None = None
    cover_artists: list[str] | None = None
    metadata_identity_key: str | None = Field(default=None, max_length=1024)
    quantity: int = Field(gt=0)
    raw_item_price: Decimal = Field(ge=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return validate_required_trimmed(value, "title")

    @field_validator("publisher")
    @classmethod
    def validate_publisher(cls, value: str) -> str:
        return validate_required_trimmed(value, "publisher")

    @field_validator("issue_number")
    @classmethod
    def validate_issue_number(cls, value: str) -> str:
        return validate_required_trimmed(value, "issue_number")

    @field_validator(
        "cover_name",
        "printing",
        "ratio",
        "variant_type",
        "cover_artist",
        "metadata_identity_key",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("writers", "artists", "cover_artists", mode="before")
    @classmethod
    def normalize_optional_creators(
        cls,
        value: list[str] | str | None,
    ) -> list[str] | None:
        return normalize_optional_text_list(value)


class OrderCreate(BaseModel):
    retailer: str = Field(min_length=1, max_length=120)
    order_date: date
    source_type: str | None = Field(default=None, max_length=100)
    shipping_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    items: list[OrderItemCreate] = Field(min_length=1)

    @field_validator("retailer")
    @classmethod
    def validate_retailer(cls, value: str) -> str:
        return validate_required_trimmed(value, "retailer")

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class OrderCreateResponse(BaseModel):
    order_id: int
    total_items: int
    total_copies_created: int
    all_in_total: Decimal


class OrderListRow(BaseModel):
    order_id: int
    retailer: str
    order_date: date
    source_type: str | None
    shipping_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    total_items: int
    total_copies: int
    created_at: datetime


class OrderListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[OrderListRow]


class OrderDetailItem(BaseModel):
    order_item_id: int
    publisher: str
    title: str
    release_date: date | None = None
    release_status: Literal["released", "not_released_yet", "unknown"]
    order_status: Literal["ordered", "preordered", "shipped", "received", "cancelled"]
    purchase_date: date | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    asset_state: Literal["in_hand", "ordered_not_received", "preorder_not_released_yet", "cancelled"]
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None
    quantity: int
    raw_item_price: Decimal
    allocated_shipping: Decimal
    allocated_tax: Decimal
    all_in_unit_cost: Decimal
    inventory_copy_ids: list[int]


class OrderDetailResponse(BaseModel):
    order_id: int
    retailer: str
    order_date: date
    source_type: str | None
    shipping_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    created_at: datetime
    items: list[OrderDetailItem]
