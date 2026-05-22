from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ParseOrderRequest(BaseModel):
    raw_text: str = Field(min_length=1)

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("raw_text is required")
        return trimmed


class AiDraftOrderItem(BaseModel):
    publisher: str | None = None
    title: str | None = None
    issue_number: str | None = None
    cover_name: str | None = None
    printing: str | None = None
    ratio: str | None = None
    variant_type: str | None = None
    cover_artist: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    raw_item_price: Decimal | None = Field(default=None, ge=0)


DraftSourceType = Literal["ai_draft", "manual_draft", "gmail_draft"]


class ParseOrderResponse(BaseModel):
    retailer: str | None = None
    order_date: date | None = None
    source_type: DraftSourceType = "ai_draft"
    shipping_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    items: list[AiDraftOrderItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
