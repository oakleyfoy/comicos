from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LiveSaleSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    session_name: str = Field(min_length=1, max_length=255)
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None


class LiveSaleSessionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_name: str | None = Field(default=None, min_length=1, max_length=255)
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    session_status: str | None = Field(default=None, min_length=4, max_length=24)


class LiveSaleSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    session_name: str
    session_status: str
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime


class LiveSaleQueueItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int = Field(gt=0)
    marketplace_listing_draft_id: int = Field(gt=0)
    planned_price: Decimal | None = Field(default=None, ge=0)


class LiveSaleQueueItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_status: str = Field(min_length=4, max_length=24)
    planned_price: Decimal | None = Field(default=None, ge=0)
    actual_sale_price: Decimal | None = Field(default=None, ge=0)


class LiveSaleQueueReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_item_ids: list[int] = Field(default_factory=list)


class LiveSaleQueueItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    live_sale_session_id: int
    inventory_item_id: int
    marketplace_listing_draft_id: int
    queue_position: int
    item_status: str
    planned_price: Decimal | None = None
    actual_sale_price: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class LiveSaleClaimCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    live_sale_queue_item_id: int = Field(gt=0)
    buyer_identifier: str = Field(min_length=1, max_length=255)
    claimed_status: str = Field(default="claimed", min_length=4, max_length=24)
    claimed_price: Decimal | None = Field(default=None, ge=0)


class LiveSaleClaimUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_status: str = Field(min_length=4, max_length=24)


class LiveSaleClaimResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    live_sale_session_id: int
    live_sale_queue_item_id: int
    buyer_identifier: str
    claim_status: str
    claimed_price: Decimal | None = None
    claimed_at: datetime
    created_at: datetime


class LiveSaleEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    live_sale_session_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class LiveSalePermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class LiveSaleSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: int
    live_sessions: int
    planned_sessions: int
    ended_sessions: int
    cancelled_sessions: int


class LiveSaleClaimSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_claims: int
    claimed_claims: int
    confirmed_claims: int
    cancelled_claims: int


class LiveSaleSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LiveSaleSessionResponse] = Field(default_factory=list)
    permissions: LiveSalePermissionResponse
    summary: LiveSaleSummaryResponse
    total_items: int
    limit: int
    offset: int


class LiveSaleQueueItemListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LiveSaleQueueItemResponse] = Field(default_factory=list)
    permissions: LiveSalePermissionResponse
    total_items: int
    limit: int
    offset: int


class LiveSaleClaimListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LiveSaleClaimResponse] = Field(default_factory=list)
    permissions: LiveSalePermissionResponse
    summary: LiveSaleClaimSummaryResponse
    total_items: int
    limit: int
    offset: int


class LiveSaleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: LiveSaleSessionResponse
    permissions: LiveSalePermissionResponse
    queue_items: list[LiveSaleQueueItemResponse] = Field(default_factory=list)
    claims: list[LiveSaleClaimResponse] = Field(default_factory=list)
    events: list[LiveSaleEventResponse] = Field(default_factory=list)
