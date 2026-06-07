"""P79-01 storage foundation API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class P79StorageLocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: int | None = None
    location_kind: str
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    capacity: int | None = Field(default=None, ge=1)
    is_active: bool = True
    sort_order: int = 0
    seed_office_template: bool = False


class P79StorageLocationRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    parent_id: int | None
    location_kind: str
    name: str
    description: str
    capacity: int | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    utilization_pct: float = 0.0
    current_occupancy: int = 0
    remaining_capacity: int | None = None


class P79StorageLocationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P79StorageLocationRead] = Field(default_factory=list)
    total_items: int
    limit: int = 100
    offset: int = 0
    status: str = "OK"
    message: str = ""


class P79StorageBoxCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shelf_location_id: int
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    capacity: int = Field(default=100, ge=1, le=500)
    is_active: bool = True


class P79StorageBoxRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    shelf_location_id: int
    name: str
    description: str
    capacity: int
    is_active: bool
    current_occupancy: int
    remaining_capacity: int
    utilization_pct: float
    suggested_next_slot: int | None
    created_at: datetime
    updated_at: datetime


class P79StorageBoxListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P79StorageBoxRead] = Field(default_factory=list)
    total_items: int
    limit: int = 100
    offset: int = 0


class P79StorageAssignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    box_id: int
    slot_number: int | None = Field(default=None, ge=1)
    use_suggested_slot: bool = False


class P79StorageLocationPathSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    name: str
    id: int


class P79StorageAssignmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    inventory_copy_id: int
    box_id: int
    slot_number: int
    location_path: list[P79StorageLocationPathSegment]
    box_name: str
    assigned_at: datetime
    updated_at: datetime
    assigned_by_user_id: int | None
    series_name: str | None = None
    issue_number: str | None = None
    variant_label: str | None = None


class P79StorageSearchResultRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    series_name: str
    issue_number: str
    variant_label: str
    location_path: list[P79StorageLocationPathSegment]
    box_name: str
    slot_number: int


class P79StorageSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P79StorageSearchResultRead] = Field(default_factory=list)
    total_items: int
    query: str


class P79StorageDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_count: int
    box_count: int
    assigned_books: int
    unassigned_books: int
    total_slot_capacity: int
    occupied_slots: int
    available_slots: int
    location_utilization_pct: float
    shelf_utilization_pct: float
    box_utilization_pct: float
    recent_assignments: list[P79StorageAssignmentRead] = Field(default_factory=list)
    locations: list[P79StorageLocationRead] = Field(default_factory=list)
    boxes: list[P79StorageBoxRead] = Field(default_factory=list)
    status: str = "OK"
    message: str = ""
