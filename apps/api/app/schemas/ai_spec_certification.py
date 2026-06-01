from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AISpecCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class AISpecCertificationReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_result: str
    certification_recommendation: str
    validation_status: str
    health_status: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    domain_scores: dict[str, float] = Field(default_factory=dict)


class AISpecCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    input_score: float
    baseline_score: float
    ai_eval_score: float
    top20_score: float
    dashboard_score: float
    automation_score: float
    determinism_score: float
    operations_score: float
    readiness_score: float
    certification_result: str
    validation_status: str
    checks: list[AISpecCertificationCheckRead] = Field(default_factory=list)
    report: AISpecCertificationReportRead
    validation_summary: str = ""


class AISpecCertificationRunListRead(BaseModel):
    items: list[AISpecCertificationRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class AISpecCertificationRunTriggerResponse(BaseModel):
    run: AISpecCertificationRead


class AISpecCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    validation_status: str = "UNKNOWN"
