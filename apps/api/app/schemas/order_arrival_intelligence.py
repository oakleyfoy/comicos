from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.inventory_intelligence import KeyedCount

OrderArrivalClassification = Literal[
    "upcoming_preorder",
    "releases_this_week",
    "released_not_received",
    "expected_to_ship_soon",
    "overdue_expected_ship",
    "received_recently",
    "cancelled_order",
    "missing_release_date",
    "missing_expected_ship_date",
]


class OrderArrivalIntelRead(BaseModel):
    """Derived read-model row: one classification applied to one inventory copy."""

    intel_key: str
    inventory_copy_id: int
    classification: OrderArrivalClassification
    retailer: str
    source_type: str | None = None
    publisher: str
    title: str
    issue_number: str
    order_item_quantity: int = Field(ge=0)
    order_status: str
    release_status: str
    asset_state: str
    purchase_date: date | None = None
    release_date: date | None = None
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class OrderArrivalIntelSummaryItem(BaseModel):
    inventory_copy_id: int
    publisher: str
    title: str
    issue_number: str
    retailer: str
    classification_count: int = Field(ge=0)
    classifications: list[OrderArrivalClassification] = Field(default_factory=list)
    evidence_preview: list[str] = Field(default_factory=list)


class OrderArrivalIntelSummary(BaseModel):
    scope_user_id: int | None = None
    scope: str
    generated_as_of_date: str
    total_inventory_copies: int = Field(default=0, ge=0)
    total_intel_items: int = Field(default=0, ge=0)
    copies_tagged: int = Field(default=0, ge=0)
    by_classification: list[KeyedCount] = Field(default_factory=list)
    top_action_items: list[OrderArrivalIntelSummaryItem] = Field(default_factory=list)


class OrderArrivalIntelListResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str
    generated_as_of_date: str
    total_count: int = Field(default=0, ge=0)
    classification: OrderArrivalClassification | Literal["all"] = "all"
    retailer: str | None = None
    publisher: str | None = None
    release_date_from: date | None = None
    release_date_to: date | None = None
    expected_ship_date_from: date | None = None
    expected_ship_date_to: date | None = None
    order_status: str | Literal["all"] = "all"
    in_hand_only: bool = False
    summary: OrderArrivalIntelSummary
    items: list[OrderArrivalIntelRead] = Field(default_factory=list)


class OrderArrivalCalendarCell(BaseModel):
    inventory_copy_id: int
    title: str
    issue_number: str
    publisher: str
    retailer: str
    order_status: str
    release_status: str
    classifications: list[OrderArrivalClassification] = Field(default_factory=list)


class OrderArrivalCalendarRow(BaseModel):
    calendar_date: date
    on_release_date: list[OrderArrivalCalendarCell] = Field(default_factory=list)
    on_expected_ship_date: list[OrderArrivalCalendarCell] = Field(default_factory=list)


class OrderArrivalIntelCalendarResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str
    generated_as_of_date: str
    calendar_start: date
    calendar_end: date
    rows: list[OrderArrivalCalendarRow] = Field(default_factory=list)
