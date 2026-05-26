"""P36-02 schemas for deterministic listing exports."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

EXPORT_CHANNELS = frozenset(
    {"ebay", "whatnot", "shopify", "hipcomic", "shortboxed", "generic_csv"}
)


class ListingExportTemplateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    channel: str
    name: str
    description: str | None
    template_version: str
    column_map_json: list | dict = Field(description="Deterministic ordered column mappings")
    rules_json: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ListingExportRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: int | None = Field(default=None, ge=1)
    channel: str | None = Field(default=None, min_length=2, max_length=40)
    listing_ids: list[int] = Field(min_length=1)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ListingExportRunItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    export_run_id: int
    listing_id: int | None
    status: str
    skip_reason: str | None
    error_message: str | None
    row_number: int
    row_checksum: str | None
    created_at: datetime


class ListingExportFileRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    export_run_id: int
    file_name: str
    file_type: str
    storage_path: str
    checksum: str
    row_count: int
    created_at: datetime


class ListingExportRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    template_id: int
    channel: str
    status: str
    requested_listing_count: int
    exported_listing_count: int
    skipped_listing_count: int
    error_count: int
    replay_key: str | None
    checksum: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ListingExportRunDetailRead(ListingExportRunRead):
    items: list[ListingExportRunItemRead] = Field(default_factory=list)
    files: list[ListingExportFileRead] = Field(default_factory=list)


class ListingExportRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingExportRunRead]
    total_items: int
    limit: int
    offset: int


class ListingExportDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_run_count: int
    skipped_rows_lifetime_sum: int
    latest_completed_checksum: str | None
    recent_runs: list[ListingExportRunRead]


class OpsListingExportFileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingExportFileRead]
    total_items: int
    limit: int
    offset: int
