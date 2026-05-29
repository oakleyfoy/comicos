from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceAnalyticsPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceAnalyticsSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    snapshot_type: str
    snapshot_payload_json: dict
    generated_at: datetime


class MarketplaceMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    metric_key: str
    metric_value_json: dict
    metric_period: str
    generated_at: datetime


class MarketplacePerformanceTrendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    trend_key: str
    trend_payload_json: dict
    trend_period: str
    generated_at: datetime


class MarketplaceAnalyticsEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MarketplaceAnalyticsSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceAnalyticsSnapshotResponse] = Field(default_factory=list)
    permissions: MarketplaceAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceMetricResponse] = Field(default_factory=list)
    permissions: MarketplaceAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplacePerformanceTrendListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplacePerformanceTrendResponse] = Field(default_factory=list)
    permissions: MarketplaceAnalyticsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceAnalyticsDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: MarketplaceAnalyticsPermissionResponse
    summary: dict = Field(default_factory=dict)
    metrics: list[MarketplaceMetricResponse] = Field(default_factory=list)
    trends: list[MarketplacePerformanceTrendResponse] = Field(default_factory=list)
    snapshots: list[MarketplaceAnalyticsSnapshotResponse] = Field(default_factory=list)
    events: list[MarketplaceAnalyticsEventResponse] = Field(default_factory=list)
    latest_snapshot: MarketplaceAnalyticsSnapshotResponse | None = None
