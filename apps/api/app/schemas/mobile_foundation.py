from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobilePermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MobileDeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    device_identifier: str
    device_name: str
    device_type: str
    device_status: str
    last_seen_at: datetime | None
    created_at: datetime


class MobileSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    device_id: int
    user_id: int
    session_status: str
    started_at: datetime
    ended_at: datetime | None


class OfflineSyncContractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    contract_type: str
    contract_payload_json: dict
    created_at: datetime


class MobileFoundationEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MobileDeviceRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_identifier: str = Field(min_length=1, max_length=128)
    device_name: str = Field(min_length=1, max_length=200)
    device_type: str = Field(min_length=1, max_length=32)


class MobileDeviceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_name: str | None = Field(default=None, min_length=1, max_length=200)
    device_type: str | None = Field(default=None, min_length=1, max_length=32)
    device_status: str | None = Field(default=None, min_length=1, max_length=24)
    record_seen: bool = False


class MobileSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: int


class OfflineSyncContractCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_type: str = Field(min_length=1, max_length=32)
    contract_payload_json: dict = Field(default_factory=dict)


class MobileDeviceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobilePermissionResponse
    items: list[MobileDeviceResponse]
    total_items: int
    limit: int
    offset: int


class MobileSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobilePermissionResponse
    items: list[MobileSessionResponse]
    total_items: int
    limit: int
    offset: int


class OfflineSyncContractListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobilePermissionResponse
    items: list[OfflineSyncContractResponse]
    total_items: int
    limit: int
    offset: int


class MobileFoundationDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobilePermissionResponse
    summary: dict
    runtime_registry: dict
    recent_events: list[MobileFoundationEventResponse]
