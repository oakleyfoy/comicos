from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EbayCompImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    series: str | None = Field(default=None, max_length=255)
    issue_number: str | None = Field(default=None, max_length=64)
    variant: str | None = Field(default=None, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    upc: str | None = Field(default=None, max_length=64)
    condition: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=25, ge=1, le=100)


class EbayCompImportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "EBAY"
    import_run_id: int
    fetched: int = Field(ge=0)
    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    error_count: int = Field(ge=0)
    imported_at: datetime


class EbayCompImportRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    provider: str
    import_status: str
    search_criteria_json: dict
    fetched_count: int
    inserted_count: int
    updated_count: int
    duplicate_count: int
    error_count: int
    error_message: str | None = None
    imported_at: datetime
    completed_at: datetime
