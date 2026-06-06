from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

InventoryArrivalTrackingLane = Literal["on_the_way", "not_released_yet", "released_not_received"]


class InventoryArrivalTrackingRow(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    retailer: str
    source_type: str | None = None
    order_status: str
    release_status: str
    release_date: date | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    lane: InventoryArrivalTrackingLane


class InventoryArrivalTrackingSummary(BaseModel):
    scope_user_id: int | None = None
    generated_as_of_date: str
    not_in_hand_total: int = Field(ge=0, default=0)
    on_the_way_count: int = Field(ge=0, default=0)
    not_released_yet_count: int = Field(ge=0, default=0)
    released_not_received_count: int = Field(ge=0, default=0)


class InventoryArrivalTrackingResponse(BaseModel):
    summary: InventoryArrivalTrackingSummary
    not_released_yet_items: list[InventoryArrivalTrackingRow] = Field(default_factory=list)
