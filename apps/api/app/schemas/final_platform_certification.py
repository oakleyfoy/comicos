from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FinalPlatformCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class FinalPlatformCertificationReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_result: str
    production_recommendation: str
    validation_status: str
    health_status: str
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    domain_scores: dict[str, float] = Field(default_factory=dict)


class FinalPlatformCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    release_intelligence_score: float
    recommendation_intelligence_score: float
    pull_list_score: float
    purchase_score: float
    portfolio_score: float
    acquisition_score: float
    exit_score: float
    unified_intelligence_score: float
    daily_action_score: float
    cross_system_score: float
    executive_dashboard_score: float
    determinism_score: float
    operations_score: float
    readiness_score: float
    certification_result: str
    health_status: str
    validation_status: str
    report: FinalPlatformCertificationReportRead
    checks: list[FinalPlatformCertificationCheckRead] = Field(default_factory=list)


class FinalPlatformCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    health_status: str = "UNHEALTHY"
    validation_summary: str = ""


class FinalPlatformCertificationRunListResponse(BaseModel):
    items: list[FinalPlatformCertificationRead]
    total_items: int
    limit: int
    offset: int


class FinalPlatformCertificationRunTriggerResponse(BaseModel):
    run: FinalPlatformCertificationRead
