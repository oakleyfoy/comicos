"""P64 Collector Assistant API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class CollectorRecommendationItemRead(BaseModel):
    id: int
    owner_id: int
    lane: str
    priority_score: float
    confidence: str
    title: str
    publisher: str
    issue_number: str
    recommended_action: str
    explanation: str
    reason_codes: list[str] = Field(default_factory=list)
    release_issue_id: int | None = None
    inventory_copy_id: int | None = None
    status: str


class CollectorRecommendationsRead(BaseModel):
    run_id: int | None = None
    readiness_status: str = "SUCCESS"
    lanes: dict[str, list[CollectorRecommendationItemRead]] = Field(default_factory=dict)
    total_items: int = 0


class CollectorBriefingRead(BaseModel):
    snapshot_id: int | None = None
    run_id: int | None = None
    readiness_status: str
    week_start: date | None = None
    headline: str = ""
    briefing_json: dict = Field(default_factory=dict)
    briefing_markdown: str = ""


class CollectorHealthRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str
    health_score: float = 0.0
    health_band: str = "FAIR"
    metrics_json: dict = Field(default_factory=dict)
    risk_flags_json: list = Field(default_factory=list)


class CollectorAlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str
    action_deep_link: str


class CollectorAlertsRead(BaseModel):
    snapshot_id: int | None = None
    alert_count: int = 0
    critical_count: int = 0
    readiness_status: str = "SUCCESS"
    alerts: list[CollectorAlertRead] = Field(default_factory=list)


class CollectorDashboardRead(BaseModel):
    bundle_id: int | None = None
    run_id: int | None = None
    readiness_status: str
    platform_ready: bool = False
    dashboard_json: dict = Field(default_factory=dict)
    freshness_json: dict = Field(default_factory=dict)


class CollectorBuildResultRead(BaseModel):
    run_id: int
    status: str


class CollectorComponentCertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: str


class CollectorPlatformCertificationRead(BaseModel):
    platform_ready: bool
    briefing: dict = Field(default_factory=dict)
    lanes: dict = Field(default_factory=dict)
    executive: dict = Field(default_factory=dict)
    non_mutation: dict = Field(default_factory=dict)
    run_id: int | None = None
    checked_at: str
