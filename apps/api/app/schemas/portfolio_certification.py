from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PortfolioCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class PortfolioIntelligenceReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_result: str
    certification_recommendation: str
    validation_status: str
    health_status: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    domain_scores: dict[str, float] = Field(default_factory=dict)


class PortfolioCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    run_completeness_score: float
    missing_issue_score: float
    duplicate_analysis_score: float
    grade_candidate_score: float
    sell_candidate_score: float
    determinism_score: float
    operations_score: float
    readiness_score: float
    certification_result: str
    validation_status: str
    checks: list[PortfolioCertificationCheckRead] = Field(default_factory=list)
    report: PortfolioIntelligenceReportRead
    validation_summary: str = ""


class PortfolioCertificationRunListResponse(BaseModel):
    items: list[PortfolioCertificationRead]
    total_items: int
    limit: int
    offset: int


class PortfolioCertificationRunTriggerResponse(BaseModel):
    run: PortfolioCertificationRead


class PortfolioCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    validation_status: str = "UNKNOWN"
