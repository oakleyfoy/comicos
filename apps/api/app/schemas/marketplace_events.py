from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceEventIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int = Field(gt=0)
    external_event_identifier: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=80)
    event_payload_json: dict = Field(default_factory=dict)
    received_at: datetime | None = None


class MarketplaceEventProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_event_id: int = Field(gt=0)


class MarketplaceEventValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class MarketplaceEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    marketplace_type: str
    external_event_identifier: str
    event_type: str
    event_status: str
    event_payload_json: dict = Field(default_factory=dict)
    received_at: datetime
    processed_at: datetime | None = None
    created_at: datetime


class MarketplaceWebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    endpoint_type: str
    endpoint_status: str
    endpoint_identifier: str
    created_at: datetime


class MarketplaceEventProcessingRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_event_id: int
    processing_status: str
    processing_result_json: dict = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None


class MarketplaceEventLineageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_event_id: int | None = None
    actor_user_id: int | None = None
    lineage_event_type: str
    lineage_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceEventPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceEventSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_events: int
    received_events: int
    validated_events: int
    processed_events: int
    failed_events: int


class MarketplaceEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceEventResponse] = Field(default_factory=list)
    permissions: MarketplaceEventPermissionResponse
    summary: MarketplaceEventSummaryResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceEventProcessingRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceEventProcessingRunResponse] = Field(default_factory=list)
    permissions: MarketplaceEventPermissionResponse
    total_items: int
    limit: int
    offset: int


class MarketplaceEventDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: MarketplaceEventResponse
    validation_errors: list[MarketplaceEventValidationErrorResponse] = Field(default_factory=list)
    permissions: MarketplaceEventPermissionResponse
    processing_runs: list[MarketplaceEventProcessingRunResponse] = Field(default_factory=list)
    lineage: list[MarketplaceEventLineageResponse] = Field(default_factory=list)


class MarketplaceWebhookEndpointListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceWebhookEndpointResponse] = Field(default_factory=list)
    permissions: MarketplaceEventPermissionResponse
    total_items: int
    limit: int
    offset: int
