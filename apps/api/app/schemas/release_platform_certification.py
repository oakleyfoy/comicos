from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleasePlatformValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class ReleasePlatformValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    platform_certified: bool
    checks: list[ReleasePlatformValidationCheckRead]


class ReleasePlatformHealthComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_code: str
    title: str
    health_status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class ReleasePlatformHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    components: list[ReleasePlatformHealthComponentRead]


class ReleasePlatformImportSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_import_at: datetime | None
    last_successful_import_at: datetime | None
    last_failed_import_at: datetime | None
    last_import_status: str | None
    last_import_records_processed: int
    total_import_runs: int


class ReleasePlatformSchedulerSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduler_enabled: bool
    schedule_time_utc: str | None
    last_scheduled_run_status: str | None
    last_scheduled_run_at: datetime | None


class ReleasePlatformSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_releases: int
    total_series: int
    total_variants: int
    total_new_number_ones: int
    total_opportunities: int
    total_watchlists: int
    total_foc_alerts: int
    scheduler: ReleasePlatformSchedulerSummaryRead
    import_summary: ReleasePlatformImportSummaryRead
    platform_readiness_score: float


class ReleasePlatformCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_certified: bool
    validation_status: str
    health_status: str
    go_live_recommendation: str
    certification_date: datetime
    certification_version: str
    summary: str
    certification_notes: list[str] = Field(default_factory=list)
