"""P104 cover hydration dashboard schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class P104CoverHydrationStatusResponse(BaseModel):
    enabled: bool
    total: int = 0
    complete: int = 0
    failed: int = 0
    skipped_no_url: int = 0
    pending: int = 0
    rate_per_hour: int = 0
    eta_hours: float | None = None
    storage_root: str = ""
    downloads_per_minute: float = 30.0
    year_from: int = 2000
    year_to: int = 2026
    total_catalog_issues: int = 0
    eligible_catalog_issues: int = 0
    asset_rows: int = 0
    issues_with_asset_row: int = 0
    queue_coverage_pct: float = 0.0
    eligible_without_asset_row: int = 0
    eligible_with_url_not_queued: int = 0


class P104CoverHydrationDryRunRequest(BaseModel):
    pilot_limit: int = Field(default=100, ge=1, le=5000)
    sync_limit: int = Field(default=0, ge=0, le=500000)


class P104CoverHydrationDryRunResponse(BaseModel):
    report: dict[str, Any]


class P104CoverHydrationRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=10000)
    sync_limit: int = Field(default=0, ge=0, le=500000)
    confirm_write: str | None = None


class P104CoverHydrationRunResponse(BaseModel):
    summary: dict[str, Any]
