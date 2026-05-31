from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AcquisitionCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class AcquisitionIntelligenceReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_result: str
    certification_recommendation: str
    validation_status: str
    health_status: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    domain_scores: dict[str, float] = Field(default_factory=dict)


class AcquisitionCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    want_list_score: float
    collection_gap_score: float
    opportunity_score: float
    marketplace_score: float
    dashboard_score: float
    determinism_score: float
    operations_score: float
    readiness_score: float
    certification_result: str
    validation_status: str
    checks: list[AcquisitionCertificationCheckRead] = Field(default_factory=list)
    report: AcquisitionIntelligenceReportRead
    validation_summary: str = ""


class AcquisitionCertificationRunListResponse(BaseModel):
    items: list[AcquisitionCertificationRead]
    total_items: int
    limit: int
    offset: int


class AcquisitionCertificationRunTriggerResponse(BaseModel):
    run: AcquisitionCertificationRead


class AcquisitionCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    validation_status: str = "UNKNOWN"
