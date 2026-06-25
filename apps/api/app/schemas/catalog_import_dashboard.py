"""Schemas for GCD catalog import dashboard API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GcdImportStatusResponse(BaseModel):
    gcd_database: str
    gcd_database_exists: bool
    catalog_cache: str
    catalog_cache_exists: bool
    gcd_import_enabled: bool
    max_write_batch_limit: int
    focus_publishers: list[str]
    default_year_from: int
    default_year_to: int


class GcdImportCellStatsModel(BaseModel):
    publisher: str
    year: int
    gcd_rows: int = 0
    existing_issues: int = 0
    clean_candidates: int = 0
    variants: int = 0
    reprints: int = 0
    foreign_editions: int = 0
    conflicts: int = 0
    low_confidence: int = 0
    barcodes_available: int = 0
    estimated_scan_seconds: float = 0.0
    estimated_write_seconds: float = 0.0


class GcdImportMatrixResponse(BaseModel):
    generated_at: str
    year_from: int
    year_to: int
    elapsed_seconds: float
    job_id: int | None = None
    cells: list[GcdImportCellStatsModel]


class GcdImportScopeResponse(BaseModel):
    publisher: str
    year: int
    elapsed_seconds: float
    job_id: int | None = None
    stats: GcdImportCellStatsModel
    preview_rows: list[dict[str, Any]]


class GcdImportWriteRequest(BaseModel):
    publisher: str
    year: int
    limit: int = Field(default=100, ge=1, le=100)
    confirm_write: str = Field(description='Must be "YES" to execute')
    refresh_cache: bool = False


class GcdImportDryRunRequest(BaseModel):
    publisher: str
    year: int
    preview_limit: int = Field(default=100, ge=1, le=500)
    refresh_cache: bool = False


class GcdImportMatrixRequest(BaseModel):
    year_from: int
    year_to: int
    refresh_cache: bool = False


class GcdImportJobModel(BaseModel):
    job_id: int
    rollback_id: int
    source: str
    job_type: str
    status: str
    started_at: str | None
    completed_at: str | None
    created_at: str | None
    total_seen: int
    inserted_issues: int
    inserted_upcs: int
    skipped: int
    errors: int
    last_error: str | None
    scope: dict[str, Any]
    scope_stats: dict[str, Any] = Field(default_factory=dict)
    report: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)


class GcdImportJobListResponse(BaseModel):
    jobs: list[GcdImportJobModel]


class GcdImportJobResponse(BaseModel):
    job: GcdImportJobModel
