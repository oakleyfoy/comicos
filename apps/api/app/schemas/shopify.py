from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ShopifyConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_name: str = Field(min_length=1, max_length=160)
    shop_domain: str = Field(min_length=1, max_length=160)
    admin_api_token: str = Field(min_length=8, max_length=500)


class ShopifyAccountStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int
    marketplace_id: int
    status: str
    credentials_valid: bool


class ShopifyListingActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int
    mapping_id: int | None = None
    external_listing_id: str | None = None
    external_url: str | None = None
    sync_status: str
    publish_job_id: int | None = None
    execution_ids: list[int] = Field(default_factory=list)


class ShopifyImportOrdersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_count: int
    skipped_duplicates: int
    order_ids: list[int] = Field(default_factory=list)
    execution_id: int | None = None


class ShopifyInventorySyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: int | None = None
    synced_items: int
    execution_ids: list[int] = Field(default_factory=list)
