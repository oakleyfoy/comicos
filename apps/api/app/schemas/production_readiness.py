from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductionReadinessCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_uuid: str
    check_name: str
    subsystem: str
    check_status: str
    check_notes: str
    checked_at: datetime


class ProductionCertificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    certification_uuid: str
    certification_status: str
    readiness_score: float
    certification_notes: str
    certified_at: datetime


class ReadinessChecklistItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checklist_category: str
    item_name: str
    item_status: str
    validation_notes: str
    validated_at: datetime


class GoLiveAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_uuid: str
    assessment_status: str
    overall_score: float
    assessment_summary: str
    assessed_at: datetime


class GoLiveAssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GoLiveAssessmentRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ProductionReadinessCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductionReadinessCheckRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ReadinessChecklistListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReadinessChecklistItemRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ProductionCertificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductionCertificationRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class ProductionReadinessRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[ProductionReadinessCheckRead] = Field(default_factory=list)
    checklist_items: list[ReadinessChecklistItemRead] = Field(default_factory=list)


class ProductionCertificationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certification: ProductionCertificationRead
    assessment: GoLiveAssessmentRead


class ProductionReadinessDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    certification_status: str
    marketplace_status: str
    forecast_status: str
    data_protection_status: str
    operations_status: str
    agent_platform_status: str
    checklist_pass_count: int
    checklist_total: int
    go_live_status: str
    latest_certification: ProductionCertificationRead | None = None
    latest_assessment: GoLiveAssessmentRead | None = None


class ProductionReadinessValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    message: str = ""


class ProductionReadinessWorkflowReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int
    preorder_ok: bool = False
    acquire_ok: bool = False
    grade_ok: bool = False
    sell_ok: bool = False


class ProductionReadinessReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    health_status: str
    go_live_result: str
    go_live_recommendation: str
    validation_status: str
    domain_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    workflow: ProductionReadinessWorkflowReportRead | None = None


class ProductionReadinessRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    import_health_score: float
    inventory_health_score: float
    recommendation_health_score: float
    dashboard_health_score: float
    automation_health_score: float
    workflow_health_score: float
    operations_health_score: float
    readiness_score: float
    go_live_result: str
    health_status: str
    report: ProductionReadinessReportRead


class ProductionReadinessValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: ProductionReadinessRunRead
    checks: list[ProductionReadinessValidationCheckRead] = Field(default_factory=list)


class ProductionReadinessOpsPanelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_run_at: datetime | None = None
    readiness_score: float = 0.0
    health_status: str = "UNHEALTHY"
    go_live_result: str = "NOT_READY"
    recommendations: str = ""


class ProductionReadinessGoLiveRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation: ProductionReadinessValidationRead
