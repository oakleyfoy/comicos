from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobileOpsPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MobileOpsSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    snapshot_type: str
    snapshot_payload_json: dict
    generated_at: datetime


class MobileOpsMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    metric_key: str
    metric_value_json: dict
    metric_period: str
    generated_at: datetime


class MobileOpsDiagnosticResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    diagnostic_category: str
    diagnostic_status: str
    diagnostic_code: str
    diagnostic_message: str
    diagnostic_payload_json: dict
    created_at: datetime
    resolved_at: datetime | None = None


class MobileOpsEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MobileOpsSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileOpsSnapshotResponse] = Field(default_factory=list)
    permissions: MobileOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileOpsMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileOpsMetricResponse] = Field(default_factory=list)
    permissions: MobileOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileOpsDiagnosticListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    items: list[MobileOpsDiagnosticResponse] = Field(default_factory=list)
    permissions: MobileOpsPermissionResponse
    total_items: int
    limit: int
    offset: int


class MobileOpsDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileOpsPermissionResponse
    summary: dict = Field(default_factory=dict)
    metrics: list[MobileOpsMetricResponse] = Field(default_factory=list)
    diagnostics: list[MobileOpsDiagnosticResponse] = Field(default_factory=list)
    snapshots: list[MobileOpsSnapshotResponse] = Field(default_factory=list)
    events: list[MobileOpsEventResponse] = Field(default_factory=list)
    latest_snapshot: MobileOpsSnapshotResponse | None = None
