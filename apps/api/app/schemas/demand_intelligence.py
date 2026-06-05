"""P61 Demand Intelligence Platform API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class DemandRefreshRunRead(BaseModel):
    id: int
    trigger_type: str
    scope: str
    owner_user_id: int | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    profiles_updated: int
    issues_refreshed: int
    signals_appended: int
    source_version: str
    details_json: dict = Field(default_factory=dict)


class IssueDemandSnapshotRead(BaseModel):
    id: int
    source_name: str
    external_issue_id: int
    release_issue_id: int | None
    title: str
    pull_count: int | None
    want_count: int | None
    community_demand_score: float
    entity_rollup_score: float
    combined_demand_score: float
    confidence_score: float
    signal_sources_json: dict = Field(default_factory=dict)
    source_version: str
    refreshed_at: datetime


class DemandVelocitySnapshotRead(BaseModel):
    id: int
    release_issue_id: int | None
    external_issue_id: int
    window_days: int
    pull_delta: float
    want_delta: float
    combined_score_delta: float
    velocity_score: float
    acceleration_score: float
    trend_label: str
    confidence_score: float
    computed_at: datetime


class SpecOpportunityRowRead(BaseModel):
    id: int
    release_issue_id: int
    title: str
    opportunity_score: float
    spec_baseline_score: float | None
    demand_score: float
    velocity_score: float
    preference_fit_score: float
    horizon_bucket: str
    rationale_json: dict = Field(default_factory=dict)
    rank: int


class SpecOpportunitySnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    snapshot_at: datetime
    engine_epoch: int
    row_count: int
    rows: list[SpecOpportunityRowRead] = Field(default_factory=list)


class WeeklyCaptureScheduleRead(BaseModel):
    id: int
    release_date: date
    status: str
    owner_user_id: int | None
    certification_path: str | None
    sync_run_id: int | None
    details_json: dict = Field(default_factory=dict)
    updated_at: datetime


class PaginatedIssueDemandList(BaseModel):
    items: list[IssueDemandSnapshotRead] = Field(default_factory=list)
    total_items: int = 0
    limit: int = 50
    offset: int = 0


class PaginatedVelocityList(BaseModel):
    items: list[DemandVelocitySnapshotRead] = Field(default_factory=list)
    total_items: int = 0
    limit: int = 50
    offset: int = 0


class PaginatedScheduleList(BaseModel):
    items: list[WeeklyCaptureScheduleRead] = Field(default_factory=list)
    total_items: int = 0
    limit: int = 0
    offset: int = 0


class VelocityComputeResultRead(BaseModel):
    rows_updated: int
    windows: list[int] = Field(default_factory=list)


class SpecBuildResultRead(BaseModel):
    snapshot_id: int
    row_count: int


class AutomationDiscoverRead(BaseModel):
    schedule_rows: int


class DemandDashboardRead(BaseModel):
    latest_refresh: DemandRefreshRunRead | None
    issue_snapshot_count: int
    velocity_snapshot_count: int
    top_demand_issues: list[IssueDemandSnapshotRead] = Field(default_factory=list)


class DemandRefreshRequest(BaseModel):
    scope: str = "ALL"
    days_forward: int = 90
    owner_user_id: int | None = None


class DemandVelocityComputeRequest(BaseModel):
    window_days: list[int] = Field(default_factory=lambda: [7, 14, 28])


class SpecOpportunityBuildRequest(BaseModel):
    limit: int = 50


class PlatformCertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: datetime


class DemandPlatformCertificationBundleRead(BaseModel):
    refresh: PlatformCertificationRead
    velocity: PlatformCertificationRead
    spec: PlatformCertificationRead
    automation: PlatformCertificationRead
    platform_ready: bool
