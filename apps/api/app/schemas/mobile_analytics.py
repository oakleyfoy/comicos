from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobileAnalyticsPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MobileAnalyticsSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    snapshot_type: str
    snapshot_payload_json: dict
    generated_at: datetime


class MobileUsageMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    metric_key: str
    metric_value_json: dict
    metric_period: str
    generated_at: datetime


class MobileUsageTrendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    trend_key: str
    trend_payload_json: dict
    trend_period: str
    generated_at: datetime


class MobileAnalyticsEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MobileAnalyticsSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileAnalyticsSnapshotResponse] = Field(default_factory=list)
    permissions: MobileAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileUsageMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileUsageMetricResponse] = Field(default_factory=list)
    permissions: MobileAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileUsageTrendListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileUsageTrendResponse] = Field(default_factory=list)
    permissions: MobileAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileAnalyticsDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileAnalyticsPermissionResponse
    summary: dict = Field(default_factory=dict)
    metrics: list[MobileUsageMetricResponse] = Field(default_factory=list)
    trends: list[MobileUsageTrendResponse] = Field(default_factory=list)
    snapshots: list[MobileAnalyticsSnapshotResponse] = Field(default_factory=list)
    events: list[MobileAnalyticsEventResponse] = Field(default_factory=list)
    latest_snapshot: MobileAnalyticsSnapshotResponse | None = None
