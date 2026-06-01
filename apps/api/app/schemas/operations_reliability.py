from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pull_list_automation import PullListAutomationOpsPanelRead
from app.schemas.pull_list_certification import PullListCertificationOpsPanelRead
from app.schemas.portfolio_certification import PortfolioCertificationOpsPanelRead
from app.schemas.acquisition_certification import AcquisitionCertificationOpsPanelRead
from app.schemas.exit_certification import ExitCertificationOpsPanelRead
from app.schemas.final_platform_certification import FinalPlatformCertificationOpsPanelRead
from app.schemas.future_release_certification import FutureReleaseCertificationOpsPanelRead
from app.schemas.industry_scanner_automation import IndustryScannerAutomationOpsPanelRead
from app.schemas.industry_scanner_certification import IndustryScannerCertificationOpsPanelRead
from app.schemas.spec_automation import SpecAutomationOpsPanelRead
from app.schemas.ai_spec_certification import AISpecCertificationOpsPanelRead
from app.schemas.production_readiness import ProductionReadinessOpsPanelRead


class PlatformHealthCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_uuid: str
    subsystem: str
    health_status: str
    health_score: float
    check_payload_json: dict[str, object]
    checked_at: datetime


class ReliabilityIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_uuid: str
    subsystem: str
    issue_type: str
    severity: str
    issue_status: str
    issue_payload_json: dict[str, object]
    detected_at: datetime


class JobHealthMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    average_duration_ms: int
    measured_at: datetime


class QueueHealthMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    queue_name: str
    queued_count: int
    running_count: int
    failed_count: int
    measured_at: datetime


class RecoveryRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_uuid: str
    subsystem: str
    recommendation_type: str
    title: str
    description: str
    priority_score: float
    created_at: datetime


class OperationsReliabilitySummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_score: float
    platform_health_status: str
    open_issue_count: int
    recommendation_count: int


class OperationsReliabilityDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: OperationsReliabilitySummaryRead
    health_checks: list[PlatformHealthCheckRead] = Field(default_factory=list)
    issues: list[ReliabilityIssueRead] = Field(default_factory=list)
    job_metrics: list[JobHealthMetricRead] = Field(default_factory=list)
    queue_metrics: list[QueueHealthMetricRead] = Field(default_factory=list)
    recommendations: list[RecoveryRecommendationRead] = Field(default_factory=list)
    pull_list_automation: PullListAutomationOpsPanelRead | None = None
    pull_list_certification: PullListCertificationOpsPanelRead | None = None
    portfolio_certification: PortfolioCertificationOpsPanelRead | None = None
    acquisition_certification: AcquisitionCertificationOpsPanelRead | None = None
    exit_certification: ExitCertificationOpsPanelRead | None = None
    final_platform_certification: FinalPlatformCertificationOpsPanelRead | None = None
    production_readiness: ProductionReadinessOpsPanelRead | None = None
    future_release_certification: FutureReleaseCertificationOpsPanelRead | None = None
    industry_scanner_automation: IndustryScannerAutomationOpsPanelRead | None = None
    industry_scanner_certification: IndustryScannerCertificationOpsPanelRead | None = None
    spec_automation: SpecAutomationOpsPanelRead | None = None
    ai_spec_certification: AISpecCertificationOpsPanelRead | None = None


class PlatformHealthCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PlatformHealthCheckRead]
    total_items: int
    limit: int
    offset: int


class ReliabilityIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReliabilityIssueRead]
    total_items: int
    limit: int
    offset: int


class JobHealthMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[JobHealthMetricRead]
    total_items: int
    limit: int
    offset: int


class QueueHealthMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QueueHealthMetricRead]
    total_items: int
    limit: int
    offset: int


class RecoveryRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecoveryRecommendationRead]
    total_items: int
    limit: int
    offset: int


class OperationsReliabilityRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ReliabilityIssueRead] = Field(default_factory=list)
    job_metrics: list[JobHealthMetricRead] = Field(default_factory=list)
    queue_metrics: list[QueueHealthMetricRead] = Field(default_factory=list)
