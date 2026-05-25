"""P36 canonical listing registry API shapes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ListingSourceType = Literal["manual", "ebay_export", "convention", "whatnot", "shopify"]
ListingStatus = Literal["DRAFT", "READY", "ACTIVE", "SOLD", "CANCELLED", "ARCHIVED"]
ListingLifecycleEventType = Literal[
    "CREATED",
    "UPDATED",
    "ACTIVATED",
    "PRICE_CHANGED",
    "SOLD",
    "CANCELLED",
    "ARCHIVED",
]
ListingImageRole = Literal["primary", "back", "detail", "gallery"]


class ListingReplayBody(BaseModel):
    """Optional deterministic replay envelopes for lifecycle POST mutations."""

    model_config = ConfigDict(extra="forbid")

    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ListingImageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover_image_id: int | None = None
    scan_session_item_id: int | None = None
    display_order: int = Field(default=0, ge=0, le=1_000_000)
    role: ListingImageRole = "gallery"


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int = Field(..., ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    source_type: ListingSourceType
    title: str = Field(..., min_length=1)
    description: str | None = None
    condition_summary: str | None = None
    asking_price_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    asking_price_currency: str | None = Field(default=None, min_length=3, max_length=8)
    quantity: int = Field(default=1, ge=1, le=100_000)

    replay_key: str | None = Field(default=None, min_length=1, max_length=128)
    skip_initial_price_history_row: bool = Field(
        default=False,
        description=(
            "When true, do not persist an append-only pricing row even if an asking amount is supplied."
        ),
    )
    images: list[ListingImageCreate] | None = None


class ListingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    source_type: ListingSourceType | None = None
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    condition_summary: str | None = None
    asking_price_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    asking_price_currency: str | None = Field(default=None, min_length=3, max_length=8)
    quantity: int | None = Field(default=None, ge=1, le=100_000)
    status: ListingStatus | None = None

    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ListingLifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    event_type: ListingLifecycleEventType
    prior_status: str | None
    new_status: str | None
    metadata_json: dict = Field(default_factory=dict)
    created_by_user_id: int | None
    replay_key: str | None
    created_at: datetime


class ListingPriceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    prior_amount: Decimal | None
    new_amount: Decimal
    currency: str
    reason: str | None
    replay_key: str | None
    created_at: datetime


class ListingImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    cover_image_id: int | None
    scan_session_item_id: int | None
    display_order: int
    role: ListingImageRole
    created_at: datetime


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_key: str | None
    canonical_comic_issue_id: int | None
    inventory_copy_id: int
    source_type: ListingSourceType
    status: ListingStatus
    title: str
    description: str | None
    condition_summary: str | None
    asking_price_amount: Decimal | None
    asking_price_currency: str | None
    quantity: int
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    sold_at: datetime | None
    archived_at: datetime | None


class ListingDetailRead(BaseModel):
    listing: ListingRead
    lifecycle_events_tail: list[ListingLifecycleEventRead] = Field(default_factory=list)
    price_history_tail: list[ListingPriceHistoryRead] = Field(default_factory=list)
    images: list[ListingImageRead] = Field(default_factory=list)


class ListingListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ListingStatus | None = None
    inventory_copy_id: int | None = Field(default=None, ge=1)


class ListingListResponse(BaseModel):
    items: list[ListingRead]
    total_items: int
    limit: int
    offset: int


class ListingDashboardSummary(BaseModel):
    draft_count: int
    active_count: int
    sold_count: int
    recent_events: list[ListingLifecycleEventRead]


class OpsListingLifecycleEventListResponse(BaseModel):
    items: list[ListingLifecycleEventRead]
    total_items: int
    limit: int
    offset: int


class OpsListingPriceHistoryListResponse(BaseModel):
    items: list[ListingPriceHistoryRead]
    total_items: int
    limit: int
    offset: int


class ListingOpsStatusCountRow(BaseModel):
    """Deterministic rollup row (sorted lexically by status in services)."""

    status: ListingStatus
    count: int


class ListingOpsStatusDistribution(BaseModel):
    rows: list[ListingOpsStatusCountRow]
