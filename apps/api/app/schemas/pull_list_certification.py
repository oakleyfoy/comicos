from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PullListCertificationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class PullListCertificationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    readiness_score: float
    foundation_score: float
    decision_engine_score: float
    dashboard_score: float
    automation_score: float
    determinism_score: float
    operations_score: float
    certification_result: str
    certification_recommendation: str
    validation_status: str
    checks: list[PullListCertificationCheckRead] = Field(default_factory=list)
    validation_summary: str = ""


class PullListCertificationRunListResponse(BaseModel):
    items: list[PullListCertificationRead]
    total_items: int
    limit: int
    offset: int


class PullListCertificationRunTriggerResponse(BaseModel):
    run: PullListCertificationRead


class PullListCertificationOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_certification_at: datetime | None = None
    readiness_score: float = 0.0
    certification_result: str = "NOT_READY"
    validation_status: str = "UNKNOWN"
