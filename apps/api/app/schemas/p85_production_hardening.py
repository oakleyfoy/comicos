"""P85 production hardening schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class P85PlatformCategoryRead(BaseModel):
    category: str
    status: str
    passed: bool
    warnings: int = 0
    failures: int = 0
    detail: str = ""


class P85PlatformCertificationRead(BaseModel):
    title: str
    status: str
    certified_production_release: bool
    readiness_score: float
    checks_passed: int
    warnings: int
    failures: int
    categories: list[P85PlatformCategoryRead] = Field(default_factory=list)
    production_checklist: list[dict[str, str]] = Field(default_factory=list)


class P85ProductionDashboardRead(BaseModel):
    certification_status: str
    readiness_score: float
    collector_home_ready: bool
    workflow_health_score: float
    category_summary: list[P85PlatformCategoryRead] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class P85WorkflowIssueRead(BaseModel):
    workflow: str
    severity: str
    issue_type: str
    message: str
    recommended_fix: str
    action_url: str = ""


class P85WorkflowHealthRead(BaseModel):
    health_score: float
    status: str
    issues: list[P85WorkflowIssueRead] = Field(default_factory=list)
    stale_jobs: list[str] = Field(default_factory=list)
    empty_workflows: list[str] = Field(default_factory=list)


class P85CollectorHomeActionRead(BaseModel):
    title: str
    action_type: str
    priority_score: float
    source: str
    action_url: str = ""


class P85CollectorHomeSectionRead(BaseModel):
    key: str
    title: str
    items: list[dict] = Field(default_factory=list)
    empty_hint: str = ""
    count: int = 0


class P85CollectorHomeRead(BaseModel):
    headline: str
    todays_actions: list[P85CollectorHomeActionRead] = Field(default_factory=list)
    sections: list[P85CollectorHomeSectionRead] = Field(default_factory=list)
    budget_status: dict = Field(default_factory=dict)
    portfolio_movement: dict = Field(default_factory=dict)
    generated_at: str = ""
