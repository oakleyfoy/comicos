from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConventionPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class ConventionSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    session_name: str
    session_status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class ConventionBoothResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    convention_session_id: int
    booth_name: str
    booth_status: str
    created_at: datetime


class ConventionInventoryStageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    convention_session_id: int
    inventory_item_id: int
    stage_status: str
    staged_at: datetime


class ConventionActivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    convention_session_id: int
    activity_type: str
    activity_payload_json: dict
    created_at: datetime


class ConventionEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class ConventionSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_name: str = Field(min_length=1, max_length=200)


class ConventionSessionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_status: str = Field(min_length=1, max_length=24)


class ConventionBoothCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_session_id: int
    booth_name: str = Field(min_length=1, max_length=200)


class ConventionBoothUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booth_status: str = Field(min_length=1, max_length=24)


class ConventionInventoryStageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    convention_session_id: int
    inventory_item_id: int


class ConventionSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: ConventionPermissionResponse
    items: list[ConventionSessionResponse]
    total_items: int
    limit: int
    offset: int


class ConventionBoothListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: ConventionPermissionResponse
    items: list[ConventionBoothResponse]
    total_items: int
    limit: int
    offset: int


class ConventionInventoryStageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: ConventionPermissionResponse
    items: list[ConventionInventoryStageResponse]
    total_items: int
    limit: int
    offset: int


class ConventionActivityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: ConventionPermissionResponse
    items: list[ConventionActivityResponse]
    total_items: int
    limit: int
    offset: int


class ConventionModeDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: ConventionPermissionResponse
    summary: dict
    runtime_registry: dict
    recent_events: list[ConventionEventResponse]
