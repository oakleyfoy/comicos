"""P103.5 GCD identity + UPC backfill dashboard API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GcdIdentityBackfillStatusResponse(BaseModel):
    gcd_database: str
    gcd_database_exists: bool
    catalog_cache: str
    catalog_cache_exists: bool
    gcd_enrichment_enabled: bool
    max_write_batch_limit: int
    focus_publishers: list[str]
    default_year_from: int
    default_year_to: int


class GcdIdentityBackfillDryRunRequest(BaseModel):
    publisher: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    limit: int | None = Field(default=None, ge=1)
    refresh_cache: bool = False
    all_catalog: bool = False
    benchmark: bool = False
    resume_job_id: int | None = None


class GcdIdentityBackfillWriteRequest(BaseModel):
    publisher: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    limit: int = Field(..., ge=1, le=50_000)
    confirm_write: str
    refresh_cache: bool = False
    all_catalog: bool = False
    resume_job_id: int | None = None


class GcdIdentityBackfillJobModel(BaseModel):
    job_id: int
    rollback_id: int
    source: str | None = None
    job_type: str | None = None
    status: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    total_seen: int | None = None
    updated_issues: int = 0
    inserted_upcs: int = 0
    skipped: int | None = None
    errors: int | None = None
    last_error: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    report: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] = Field(default_factory=dict)


class GcdIdentityBackfillJobResponse(BaseModel):
    job: GcdIdentityBackfillJobModel


class GcdIdentityBackfillJobListResponse(BaseModel):
    jobs: list[GcdIdentityBackfillJobModel]
