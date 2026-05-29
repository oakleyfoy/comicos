from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FEATURED_INVENTORY_SORT_MODES: tuple[str, ...] = (
    "newest",
    "recently_updated",
    "highest_value",
    "manually_selected",
)

FeaturedInventorySortMode = Literal["newest", "recently_updated", "highest_value", "manually_selected"]
StorefrontVisibilityMode = Literal["PUBLIC", "UNLISTED", "PRIVATE"]
ProfileStatusMode = Literal["ACTIVE", "DRAFT", "DISABLED"]


class DealerProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    public_slug: str
    display_name: str
    tagline: str | None = None
    description: str | None = None
    logo_asset_id: int | None = None
    banner_asset_id: int | None = None
    website_url: str | None = None
    instagram_url: str | None = None
    whatnot_url: str | None = None
    location_label: str | None = None
    profile_status: str
    created_at: datetime
    updated_at: datetime


class DealerStorefrontSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    storefront_visibility: str
    public_inventory_enabled: bool
    featured_inventory_limit: int
    featured_inventory_sort: str
    featured_manual_inventory_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PublicStorefrontInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None = None
    grade_status: str
    current_fmv: Decimal | None = None
    release_year: int | None = None


class PublicStorefrontInventoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PublicStorefrontInventoryItem]
    total_items: int
    limit: int
    offset: int


class PublicStorefrontResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: DealerProfileResponse
    settings: DealerStorefrontSettingsResponse


class DealerProfileUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_slug: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=1, max_length=200)
    tagline: str | None = Field(default=None, max_length=240)
    description: str | None = None
    logo_asset_id: int | None = None
    banner_asset_id: int | None = None
    website_url: str | None = Field(default=None, max_length=512)
    instagram_url: str | None = Field(default=None, max_length=512)
    whatnot_url: str | None = Field(default=None, max_length=512)
    location_label: str | None = Field(default=None, max_length=160)
    profile_status: ProfileStatusMode = "ACTIVE"


class DealerStorefrontSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storefront_visibility: StorefrontVisibilityMode = "PRIVATE"
    public_inventory_enabled: bool = False
    featured_inventory_limit: int = Field(default=12, ge=1, le=100)
    featured_inventory_sort: FeaturedInventorySortMode = "newest"
    featured_manual_inventory_ids: list[int] = Field(default_factory=list)
