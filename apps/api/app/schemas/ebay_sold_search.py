from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EbaySoldSearchPreviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "EBAY"
    provider_listing_id: str
    title: str
    sold_price: float
    currency: str
    shipping_price: float | None = None
    total_price: float | None = None
    sold_at: datetime | None = None
    ended_at: datetime | None = None
    condition: str | None = None
    listing_type: str | None = None
    item_url: str | None = None
    image_url: str | None = None
    seller_location: str | None = None
    raw_match_confidence: float = Field(ge=0.0, le=1.0)
    match_notes: list[str] = Field(default_factory=list)


class EbaySoldSearchPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    sold_search_available: bool
    total_items: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    items: list[EbaySoldSearchPreviewItem] = Field(default_factory=list)
