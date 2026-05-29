from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OfflineInventoryPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class OfflineInventoryRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int | None
    local_record_identifier: str
    record_payload_json: dict
    local_updated_at: datetime
    created_at: datetime


class OfflineInventoryChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    device_id: int
    inventory_item_id: int | None
    change_type: str
    change_payload_json: dict
    created_at: datetime


class OfflineSyncQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    device_id: int
    queue_status: str
    queue_payload_json: dict
    queued_at: datetime
    processed_at: datetime | None


class OfflineSyncConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    inventory_item_id: int | None
    conflict_type: str
    local_payload_json: dict
    server_payload_json: dict
    conflict_status: str
    created_at: datetime


class OfflineInventoryEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class OfflineInventoryRecordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_record_identifier: str = Field(min_length=1, max_length=128)
    inventory_item_id: int | None = None
    record_payload_json: dict = Field(default_factory=dict)
    local_updated_at: datetime | None = None


class OfflineInventoryRecordUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int | None = None
    record_payload_json: dict | None = None
    local_updated_at: datetime | None = None


class OfflineInventoryChangeRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: int
    inventory_item_id: int | None = None
    change_type: str = Field(min_length=1, max_length=24)
    change_payload_json: dict = Field(default_factory=dict)


class OfflineSyncQueueCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: int
    queue_payload_json: dict = Field(default_factory=dict)


class OfflineSyncConflictRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int | None = None
    conflict_type: str = Field(min_length=1, max_length=32)
    local_payload_json: dict = Field(default_factory=dict)
    server_payload_json: dict = Field(default_factory=dict)


class OfflineSyncConflictUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_status: str = Field(min_length=1, max_length=24)


class OfflineInventoryRecordListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: OfflineInventoryPermissionResponse
    items: list[OfflineInventoryRecordResponse]
    total_items: int
    limit: int
    offset: int


class OfflineInventoryChangeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: OfflineInventoryPermissionResponse
    items: list[OfflineInventoryChangeResponse]
    total_items: int
    limit: int
    offset: int


class OfflineSyncQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: OfflineInventoryPermissionResponse
    items: list[OfflineSyncQueueResponse]
    total_items: int
    limit: int
    offset: int


class OfflineSyncConflictListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: OfflineInventoryPermissionResponse
    items: list[OfflineSyncConflictResponse]
    total_items: int
    limit: int
    offset: int


class OfflineInventoryDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: OfflineInventoryPermissionResponse
    summary: dict
    runtime_registry: dict
    recent_records: list[OfflineInventoryRecordResponse]
    recent_events: list[OfflineInventoryEventResponse]
