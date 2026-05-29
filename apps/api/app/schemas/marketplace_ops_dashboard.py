from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceOpsPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceOpsSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    snapshot_type: str
    snapshot_payload_json: dict
    generated_at: datetime


class MarketplaceOpsMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    metric_key: str
    metric_value_json: dict
    metric_period: str
    generated_at: datetime


class MarketplaceOpsDiagnosticResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    diagnostic_category: str
    diagnostic_status: str
    diagnostic_code: str
    diagnostic_message: str
    diagnostic_payload_json: dict
    created_at: datetime
    resolved_at: datetime | None = None


class MarketplaceOpsEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MarketplaceOpsSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOpsSnapshotResponse] = Field(default_factory=list)
    permissions: MarketplaceOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceOpsMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOpsMetricResponse] = Field(default_factory=list)
    permissions: MarketplaceOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceOpsDiagnosticListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceOpsDiagnosticResponse] = Field(default_factory=list)
    permissions: MarketplaceOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceOpsDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: MarketplaceOpsPermissionResponse
    summary: dict = Field(default_factory=dict)
    metrics: list[MarketplaceOpsMetricResponse] = Field(default_factory=list)
    diagnostics: list[MarketplaceOpsDiagnosticResponse] = Field(default_factory=list)
    snapshots: list[MarketplaceOpsSnapshotResponse] = Field(default_factory=list)
    events: list[MarketplaceOpsEventResponse] = Field(default_factory=list)
    latest_snapshot: MarketplaceOpsSnapshotResponse | None = None
