"""P36-05 schemas for convention / show operations."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ConventionEventType = Literal["convention", "local_show", "trade_night", "private_event", "popup"]
ConventionEventStatus = Literal["PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"]
ConventionAssignmentType = Literal["wall", "showcase", "bin", "featured", "reserve"]
ConventionMovementType = Literal["ASSIGNED", "MOVED", "REMOVED", "SOLD", "RETURNED", "HOLD"]
ConventionPricingSource = Literal["default_inventory", "convention_override", "negotiated"]
ConventionSaleSessionStatus = Literal["OPEN", "CLOSED"]


class ConventionReplayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    venue: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    start_date: date
    end_date: date
    event_type: ConventionEventType
    notes: str | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionEventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    venue: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_type: ConventionEventType | None = None
    notes: str | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_key: str | None
    name: str
    venue: str | None
    city: str | None
    state: str | None
    country: str | None
    start_date: date
    end_date: date
    event_type: ConventionEventType
    status: ConventionEventStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    completed_at: datetime | None


class ConventionAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_event_id: int = Field(ge=1)
    inventory_item_id: int = Field(ge=1)
    assignment_type: ConventionAssignmentType
    local_price_amount: Decimal | None = None
    local_price_currency: str | None = Field(default=None, min_length=3, max_length=8)
    display_location: str | None = None
    priority_rank: int | None = Field(default=None, ge=0)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convention_event_id: int
    inventory_item_id: int
    replay_key: str | None
    assignment_type: ConventionAssignmentType
    local_price_amount: Decimal | None
    local_price_currency: str | None
    display_location: str | None
    priority_rank: int | None
    assigned_at: datetime
    removed_at: datetime | None
    created_at: datetime


class ConventionMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_event_id: int = Field(ge=1)
    inventory_item_id: int = Field(ge=1)
    movement_type: ConventionMovementType
    from_location: str | None = None
    to_location: str | None = None
    notes: str | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convention_event_id: int
    inventory_item_id: int
    replay_key: str | None
    movement_type: ConventionMovementType
    from_location: str | None
    to_location: str | None
    notes: str | None
    created_by_user_id: int
    created_at: datetime


class ConventionPriceSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_event_id: int = Field(ge=1)
    inventory_item_id: int = Field(ge=1)
    price_amount: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=8)
    pricing_source: ConventionPricingSource
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionPriceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convention_event_id: int
    inventory_item_id: int
    replay_key: str | None
    price_amount: Decimal
    currency: str
    pricing_source: ConventionPricingSource
    created_at: datetime


class ConventionSaleSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_event_id: int = Field(ge=1)
    notes: str | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConventionSaleSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convention_event_id: int
    owner_user_id: int
    replay_key: str | None
    status: ConventionSaleSessionStatus
    opened_at: datetime
    closed_at: datetime | None
    notes: str | None
    created_at: datetime


class ConventionDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_convention_count: int
    assigned_inventory_count: int
    wall_book_count: int
    showcase_count: int
    active_sale_session_count: int
    recent_events: list[ConventionEventRead] = Field(default_factory=list)


class ConventionEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConventionEventRead]
    total_items: int
    limit: int
    offset: int


class ConventionAssignmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConventionAssignmentRead]
    total_items: int
    limit: int
    offset: int


class ConventionMovementListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConventionMovementRead]
    total_items: int
    limit: int
    offset: int


class ConventionPriceSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConventionPriceSnapshotRead]
    total_items: int
    limit: int
    offset: int


class ConventionSaleSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConventionSaleSessionRead]
    total_items: int
    limit: int
    offset: int
