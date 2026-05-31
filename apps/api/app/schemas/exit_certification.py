from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExitCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class ExitIntelligenceReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_result: str
    certification_recommendation: str
    validation_status: str
    health_status: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    domain_scores: dict[str, float] = Field(default_factory=dict)


class ExitCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    exit_candidate_score: float
    hold_sell_score: float
    grade_before_sell_score: float
    portfolio_rebalancing_score: float
    dashboard_score: float
    determinism_score: float
    operations_score: float
    readiness_score: float
    certification_result: str
    validation_status: str
    checks: list[ExitCertificationCheckRead] = Field(default_factory=list)
    report: ExitIntelligenceReportRead
    validation_summary: str = ""


class ExitCertificationRunListResponse(BaseModel):
    items: list[ExitCertificationRead]
    total_items: int
    limit: int
    offset: int


class ExitCertificationRunTriggerResponse(BaseModel):
    run: ExitCertificationRead


class ExitCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    validation_status: str = "UNKNOWN"
