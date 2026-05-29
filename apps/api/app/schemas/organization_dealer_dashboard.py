from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

METRIC_GROUPS: tuple[str, ...] = (
    "inventory",
    "reviews",
    "assignments",
    "storefront",
    "activity",
    "security",
    "notifications",
)

MetricGroup = Literal[
    "inventory",
    "reviews",
    "assignments",
    "storefront",
    "activity",
    "security",
    "notifications",
]

DASHBOARD_SECTIONS: tuple[str, ...] = (
    "inventory",
    "reviews",
    "activity",
    "storefront",
    "notifications",
    "security",
)

METRIC_KEYS: tuple[str, ...] = (
    "active_inventory_count",
    "pending_reviews_count",
    "assigned_inventory_count",
    "unread_notifications_count",
    "active_staff_count",
    "storefront_public_inventory_count",
    "recent_activity_count",
    "active_org_sessions_count",
)

LINEAGE_DASHBOARD_PREFIX = "lineage."

DEFAULT_METRIC_PERIOD = "current"


class OrganizationDealerDashboardSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    snapshot_type: str
    snapshot_payload_json: dict[str, object] = Field(default_factory=dict)
    generated_at: datetime


class OrganizationDealerOperationalMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    metric_key: str
    metric_value_json: dict[str, object] = Field(default_factory=dict)
    metric_group: str
    metric_period: str
    generated_at: datetime


class OrganizationDealerDashboardEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    event_type: str
    event_payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class OrganizationDealerDashboardSectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_key: str
    metrics: dict[str, object] = Field(default_factory=dict)


class OrganizationDealerDashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    snapshot: OrganizationDealerDashboardSnapshotResponse | None = None
    sections: list[OrganizationDealerDashboardSectionSummary]
    generated_at: datetime


class OrganizationDealerDashboardSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationDealerDashboardSnapshotResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationDealerOperationalMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationDealerOperationalMetricResponse]
    total_items: int
    limit: int
    offset: int
