from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class P86ReleaseLifecyclePlanItemRead(BaseModel):
    target_release_date: date
    lifecycle_stage: str
    status: str = "NOT_STARTED"
    issue_count: int | None = None
    variant_count: int | None = None
    elapsed_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    run_id: int | None = None


class P86ReleaseLifecyclePlanRead(BaseModel):
    anchor_release_date: date
    run_date: date
    items: list[P86ReleaseLifecyclePlanItemRead] = Field(default_factory=list)


class P86ReleaseLifecycleRunRead(BaseModel):
    id: int
    owner_id: int
    run_date: date
    anchor_release_date: date
    target_release_date: date
    lifecycle_stage: str
    command: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = None
    parent_queue_count: int | None = None
    parent_captured_count: int | None = None
    issue_count: int | None = None
    variant_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    raw_path: str = ""
    crosswalk_skipped: bool = True
    created_at: datetime
    updated_at: datetime


class P86ReleaseLifecycleRunListRead(BaseModel):
    items: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    total_items: int = 0
    limit: int = 50
    offset: int = 0


class P86ReleaseLifecycleLatestReportRead(BaseModel):
    status: str = "EMPTY"
    title: str = ""
    body: str = ""
    created_at: datetime | None = None
    runs: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    action_url: str = "/release-lifecycle"
    report_id: int | None = None


class P86ReleaseLifecycleAutomationRead(BaseModel):
    has_completed_weekly_run: bool = False
    cron_setup_hint: str = ""
    last_report_at: datetime | None = None
    last_report_status: str | None = None


class P86ReleaseLifecycleDashboardRead(BaseModel):
    anchor_release_date: date
    run_date: date
    this_week_plan: list[P86ReleaseLifecyclePlanItemRead] = Field(default_factory=list)
    recent_runs: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    failed_or_blocked: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    upcoming_lifecycle_dates: list[P86ReleaseLifecyclePlanItemRead] = Field(default_factory=list)
    latest_successful: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    active_running_count: int = 0
    latest_report: P86ReleaseLifecycleLatestReportRead = Field(default_factory=P86ReleaseLifecycleLatestReportRead)
    automation: P86ReleaseLifecycleAutomationRead = Field(default_factory=P86ReleaseLifecycleAutomationRead)


class P86ReleaseLifecycleWeeklyRunResponse(BaseModel):
    runs: list[P86ReleaseLifecycleRunRead] = Field(default_factory=list)
    skipped: bool = False
    message: str = ""
    report_id: int | None = None
