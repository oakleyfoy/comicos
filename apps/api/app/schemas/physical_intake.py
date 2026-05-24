"""Physical intake / receiving workflow (deterministic reads; explicit mutations only)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.order_arrival_intelligence import OrderArrivalClassification

PhysicalIntakeState = Literal[
    "awaiting_release",
    "released_awaiting_receipt",
    "received_pending_scan",
    "received_scanned",
    "intake_blocked",
    "cancelled",
    "completed",
]


PhysicalIntakeDashboardBucket = Literal[
    "released_not_received",
    "received_pending_scan",
    "overdue_expected_ship",
    "missing_release_date",
    "missing_expected_ship_date",
    "cancelled",
    "completed",
]


class MarkInventoryReceivedPayload(BaseModel):
    received_at: datetime | None = Field(
        default=None,
        description="Explicit receipt timestamp (UTC interpreted by server storage). Omit to default to deterministic server UTC now.",
    )


class CreatePhysicalIntakeScanSessionPayload(BaseModel):
    inventory_copy_ids: list[int] = Field(min_length=1, description="Selected inventory copies that are already marked received")


class PhysicalIntakeItemRead(BaseModel):
    inventory_copy_id: int
    order_item_id: int
    order_id: int
    intake_state: PhysicalIntakeState
    retailer: str
    publisher: str
    title: str
    issue_number: str
    purchase_date: date | None = None
    release_date: date | None = None
    release_status: str
    order_status: str
    asset_state: str
    expected_ship_date: date | None = None
    received_at: datetime | None = None
    has_cover_scan: bool = False
    ocr_complete_on_primary_cover: bool = False
    dashboard_buckets: list[PhysicalIntakeDashboardBucket] = Field(default_factory=list)
    order_arrival_classifications: list[OrderArrivalClassification] = Field(default_factory=list)


class PhysicalIntakeListResponse(BaseModel):
    generated_as_of: date
    items: list[PhysicalIntakeItemRead] = Field(default_factory=list)


class PhysicalIntakeSummaryCounts(BaseModel):
    released_not_received: int = 0
    received_pending_scan: int = 0
    overdue_expected_ship: int = 0
    missing_release_date: int = 0
    missing_expected_ship_date: int = 0
    cancelled: int = 0
    completed: int = 0
    awaiting_release: int = 0
    released_awaiting_receipt: int = 0
    intake_blocked: int = 0
    received_scanned: int = 0


class PhysicalIntakeSummaryResponse(BaseModel):
    generated_as_of: date
    counts: PhysicalIntakeSummaryCounts

