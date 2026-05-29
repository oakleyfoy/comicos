from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceListingValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class MarketplaceListingDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    inventory_item_id: int = Field(gt=0)
    listing_title: str = Field(min_length=1, max_length=500)
    listing_description: str | None = Field(default=None, max_length=8000)
    listing_price: Decimal | None = Field(default=None, ge=0)
    listing_currency: str = Field(default="USD", min_length=3, max_length=8)
    listing_quantity: int = Field(default=1, ge=1, le=9999)


class MarketplaceListingDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_title: str | None = Field(default=None, min_length=1, max_length=500)
    listing_description: str | None = Field(default=None, max_length=8000)
    listing_price: Decimal | None = Field(default=None, ge=0)
    listing_currency: str | None = Field(default=None, min_length=3, max_length=8)
    listing_quantity: int | None = Field(default=None, ge=1, le=9999)
    listing_status: str | None = Field(default=None, min_length=4, max_length=24)


class MarketplaceListingDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    inventory_item_id: int
    listing_title: str
    listing_description: str | None = None
    listing_price: Decimal | None = None
    listing_currency: str
    listing_quantity: int
    listing_status: str
    validation_status: str
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class MarketplaceListingProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_listing_draft_id: int
    marketplace_type: str
    projection_payload_json: dict = Field(default_factory=dict)
    projection_status: str
    generated_at: datetime


class MarketplaceListingEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_listing_draft_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceListingPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceListingDraftDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: MarketplaceListingDraftResponse
    validation_errors: list[MarketplaceListingValidationErrorResponse] = Field(default_factory=list)
    permissions: MarketplaceListingPermissionResponse
    listing_events: list[MarketplaceListingEventResponse] = Field(default_factory=list)
    projections: list[MarketplaceListingProjectionResponse] = Field(default_factory=list)


class MarketplaceListingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingDraftResponse] = Field(default_factory=list)
    permissions: MarketplaceListingPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceListingProjectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceListingProjectionResponse] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
