from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobileScanPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class ScanCaptureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    device_id: int
    scan_type: str
    scan_value: str
    normalized_value: str
    scan_status: str
    created_at: datetime


class ScanLookupResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    scan_capture_id: int
    lookup_type: str
    lookup_payload_json: dict
    created_at: datetime


class IntakeStagingRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    scan_capture_id: int
    staging_status: str
    staging_payload_json: dict
    created_at: datetime
    updated_at: datetime


class ScanEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class ScanCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: int
    scan_type: str = Field(min_length=1, max_length=32)
    scan_value: str = Field(min_length=1, max_length=512)


class ScanCaptureDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture: ScanCaptureResponse
    lookup_results: list[ScanLookupResultResponse]


class IntakeStagingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_capture_id: int
    staging_payload_json: dict = Field(default_factory=dict)


class IntakeStagingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staging_status: str = Field(min_length=1, max_length=24)


class ScanCaptureListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileScanPermissionResponse
    items: list[ScanCaptureResponse]
    total_items: int
    limit: int
    offset: int


class ScanLookupListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileScanPermissionResponse
    items: list[ScanLookupResultResponse]
    total_items: int
    limit: int
    offset: int


class IntakeStagingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileScanPermissionResponse
    items: list[IntakeStagingRecordResponse]
    total_items: int
    limit: int
    offset: int


class MobileScanningDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileScanPermissionResponse
    summary: dict
    runtime_registry: dict
    recent_events: list[ScanEventResponse]
