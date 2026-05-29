from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShopifyPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class ShopifyStorefrontCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    storefront_name: str = Field(min_length=1, max_length=255)
    storefront_identifier: str = Field(min_length=1, max_length=255)
    storefront_status: str = Field(default="draft", min_length=4, max_length=32)


class ShopifyStorefrontResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    storefront_name: str
    storefront_status: str
    storefront_identifier: str
    created_at: datetime


class ShopifyProductMappingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int = Field(gt=0)
    marketplace_listing_draft_id: int = Field(gt=0)
    storefront_product_identifier: str = Field(min_length=1, max_length=255)
    mapping_status: str = Field(default="mapped", min_length=4, max_length=24)


class ShopifyProductMappingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storefront_product_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    mapping_status: str | None = Field(default=None, min_length=4, max_length=24)


class ShopifyProductMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int
    marketplace_listing_draft_id: int
    storefront_product_identifier: str
    mapping_status: str
    created_at: datetime
    updated_at: datetime


class ShopifySyncStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    storefront_id: int
    sync_status: str
    sync_payload_json: dict
    last_sync_at: datetime | None = None
    created_at: datetime


class ShopifySyncEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    storefront_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class ShopifyStorefrontListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ShopifyStorefrontResponse] = Field(default_factory=list)
    permissions: ShopifyPermissionResponse
    total_items: int
    limit: int
    offset: int


class ShopifyProductMappingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ShopifyProductMappingResponse] = Field(default_factory=list)
    permissions: ShopifyPermissionResponse
    total_items: int
    limit: int
    offset: int


class ShopifySyncStateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ShopifySyncStateResponse] = Field(default_factory=list)
    permissions: ShopifyPermissionResponse
    total_items: int
    limit: int
    offset: int


class ShopifySyncSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storefront_id: int = Field(gt=0)


class ShopifySyncSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storefront: ShopifyStorefrontResponse
    sync_state: ShopifySyncStateResponse | None = None
    projection_payload_json: dict = Field(default_factory=dict)
    mappings: list[ShopifyProductMappingResponse] = Field(default_factory=list)


class ShopifySyncOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: ShopifyPermissionResponse
    storefronts: list[ShopifyStorefrontResponse] = Field(default_factory=list)
    mappings: list[ShopifyProductMappingResponse] = Field(default_factory=list)
    sync_states: list[ShopifySyncStateResponse] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
