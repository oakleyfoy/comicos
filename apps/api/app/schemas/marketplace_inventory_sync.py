from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceInventorySyncRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int | None = Field(default=None, gt=0)
    sync_run_type: str = Field(default="manual_sync", min_length=4, max_length=32)


class MarketplaceInventoryReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_account_id: int | None = Field(default=None, gt=0)


class MarketplaceInventoryStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int
    marketplace_listing_draft_id: int
    marketplace_listing_identifier: str
    inventory_item_id: int
    local_quantity: int
    marketplace_quantity: int
    sync_status: str
    last_sync_at: datetime
    created_at: datetime


class MarketplaceInventorySyncRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    sync_run_type: str
    sync_status: str
    records_processed: int
    conflicts_detected: int
    started_at: datetime
    completed_at: datetime | None = None


class MarketplaceInventoryConflictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_inventory_state_id: int
    conflict_type: str
    local_value_json: dict = Field(default_factory=dict)
    marketplace_value_json: dict = Field(default_factory=dict)
    conflict_status: str
    detected_at: datetime
    resolved_at: datetime | None = None


class MarketplaceInventorySyncEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    sync_run_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceInventorySyncPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MarketplaceInventoryDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_states: int
    pending_states: int
    failed_states: int
    active_conflicts: int
    completed_runs: int
    failed_runs: int


class MarketplaceInventorySyncSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostics: MarketplaceInventoryDiagnosticsResponse
    recent_runs: list[MarketplaceInventorySyncRunResponse] = Field(default_factory=list)
    recent_conflicts: list[MarketplaceInventoryConflictResponse] = Field(default_factory=list)
    recent_states: list[MarketplaceInventoryStateResponse] = Field(default_factory=list)
    permissions: MarketplaceInventorySyncPermissionResponse


class MarketplaceInventoryReconciliationEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_id: int
    marketplace_listing_identifier: str
    inventory_item_id: int
    local_quantity: int
    marketplace_quantity: int
    conflict_types: list[str] = Field(default_factory=list)


class MarketplaceInventoryReconciliationReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostics: MarketplaceInventoryDiagnosticsResponse
    entries: list[MarketplaceInventoryReconciliationEntryResponse] = Field(default_factory=list)
    conflicts: list[MarketplaceInventoryConflictResponse] = Field(default_factory=list)


class MarketplaceInventoryStateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventoryStateResponse] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceInventorySyncRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventorySyncRunResponse] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketplaceInventoryConflictListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInventoryConflictResponse] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
