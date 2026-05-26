"""P36-07 dealer dashboard API contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DealerDashboardAlertType = Literal[
    "STALE_LISTING",
    "EXPORT_FAILURE",
    "LOW_COMPLETENESS",
    "LOW_LIQUIDITY",
    "CONVENTION_PRICING_MISSING",
    "MISSING_PRIMARY_IMAGE",
]

DealerDashboardAlertSeverity = Literal["info", "warning", "critical"]

DealerDashboardFeedEventType = Literal[
    "LISTING_CREATED",
    "LISTING_SOLD",
    "EXPORT_COMPLETED",
    "EXPORT_FAILED",
    "SALE_RECORDED",
    "STALE_DETECTED",
    "CONVENTION_ASSIGNED",
    "LIQUIDITY_UPDATED",
]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class DealerDashboardGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = Field(default=None, description="Defaults to UTC calendar date when omitted.")
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)

    _trim_replay_key = field_validator("replay_key", mode="before")(_trim)


class DealerDashboardMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dashboard_snapshot_id: int
    metric_key: str
    metric_value_decimal: Decimal | None = None
    metric_value_text: str | None = None
    metric_metadata_json: dict | None = None
    created_at: datetime


class DealerDashboardSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_key: str | None = None
    active_listing_count: int
    export_ready_count: int
    incomplete_listing_count: int
    stale_listing_count: int
    active_convention_count: int
    assigned_convention_inventory_count: int
    open_sale_session_count: int
    gross_sales_30d: Decimal
    net_sales_30d: Decimal
    realized_profit_30d: Decimal
    liquidity_high_count: int
    liquidity_low_count: int
    export_run_count_30d: int
    failed_export_count_30d: int
    checksum: str
    snapshot_date: date
    created_at: datetime


class DealerDashboardGetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: DealerDashboardSnapshotRead | None


class DealerDashboardGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: DealerDashboardSnapshotRead


class DealerDashboardAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    dashboard_snapshot_id: int
    alert_type: DealerDashboardAlertType | str
    severity: DealerDashboardAlertSeverity | str
    alert_replay_key: str
    source_listing_id: int | None = None
    source_inventory_item_id: int | None = None
    source_export_run_id: int | None = None
    source_convention_event_id: int | None = None
    message: str
    acknowledged_at: datetime | None = None
    created_at: datetime


class DealerDashboardFeedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    deterministic_key: str
    dashboard_snapshot_id: int | None = None
    event_type: DealerDashboardFeedEventType | str
    source_id: int | None = None
    summary: str
    metadata_json: dict | None = None
    created_at: datetime


class DealerDashboardMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerDashboardMetricRead]
    total_items: int
    limit: int
    offset: int


class DealerDashboardAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerDashboardAlertRead]
    total_items: int
    limit: int
    offset: int


class DealerDashboardFeedListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerDashboardFeedEventRead]
    total_items: int
    limit: int
    offset: int
