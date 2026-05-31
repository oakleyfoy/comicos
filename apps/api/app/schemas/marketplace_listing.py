from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceListingVariantWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_code: str = Field(min_length=1, max_length=80)
    variant_name: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=0, le=9999)
    price: Decimal = Field(ge=0)


class MarketplaceListingVariantRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    listing_id: int
    variant_code: str
    variant_name: str
    sku: str | None = None
    quantity: int
    price: Decimal
    created_at: datetime
    updated_at: datetime


class MarketplaceListingImageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: str = Field(min_length=1)
    image_type: str = Field(min_length=1, max_length=80)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_primary: bool = False


class MarketplaceListingImageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    listing_id: int
    image_url: str
    image_type: str
    sort_order: int
    is_primary: bool
    created_at: datetime


class MarketplaceListingPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_type: str = Field(default="ASKING", min_length=1, max_length=80)
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    effective_at: datetime | None = None


class MarketplaceListingPriceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    listing_id: int
    price_type: str
    amount: Decimal
    currency: str
    effective_at: datetime
    created_at: datetime


class MarketplaceListingMappingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: int = Field(gt=0)
    marketplace_account_id: int | None = Field(default=None, gt=0)
    external_listing_id: str | None = Field(default=None, max_length=200)
    external_url: str | None = Field(default=None)
    sync_status: str = Field(default="PENDING", min_length=1, max_length=24)


class MarketplaceListingMappingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    listing_id: int
    marketplace_id: int
    marketplace_account_id: int | None = None
    external_listing_id: str | None = None
    external_url: str | None = None
    sync_status: str
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MarketplaceListingStatusHistoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    listing_id: int
    previous_status: str | None = None
    new_status: str
    reason: str | None = None
    changed_at: datetime


class MarketplaceListingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    inventory_copy_id: int | None = None
    listing_uuid: str
    listing_title: str
    listing_description: str | None = None
    listing_type: str
    condition_label: str
    grade_label: str | None = None
    asking_price: Decimal
    currency: str
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime


class MarketplaceListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int | None = Field(default=None, gt=0)
    listing_title: str = Field(min_length=1, max_length=500)
    listing_description: str | None = Field(default=None, max_length=8000)
    listing_type: str = Field(min_length=1, max_length=80)
    condition_label: str = Field(min_length=1, max_length=120)
    grade_label: str | None = Field(default=None, max_length=120)
    asking_price: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    quantity: int = Field(default=1, ge=0, le=9999)
    variants: list[MarketplaceListingVariantWrite] = Field(default_factory=list)


class MarketplaceListingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int | None = Field(default=None, gt=0)
    listing_title: str | None = Field(default=None, min_length=1, max_length=500)
    listing_description: str | None = Field(default=None, max_length=8000)
    listing_type: str | None = Field(default=None, min_length=1, max_length=80)
    condition_label: str | None = Field(default=None, min_length=1, max_length=120)
    grade_label: str | None = Field(default=None, max_length=120)
    asking_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    quantity: int | None = Field(default=None, ge=0, le=9999)
    variants: list[MarketplaceListingVariantWrite] | None = None


class MarketplaceListingDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing: MarketplaceListingRead
    variants: list[MarketplaceListingVariantRead] = Field(default_factory=list)
    images: list[MarketplaceListingImageRead] = Field(default_factory=list)
    prices: list[MarketplaceListingPriceRead] = Field(default_factory=list)
    status_history: list[MarketplaceListingStatusHistoryRead] = Field(default_factory=list)
    mappings: list[MarketplaceListingMappingRead] = Field(default_factory=list)


class MarketplaceListingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceListingPriceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingPriceRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceListingImageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingImageRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceListingMappingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingMappingRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
