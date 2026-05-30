from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentMetricSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_uuid: str
    snapshot_date: date
    generated_at: datetime
    scope: str
    summary_json: dict[str, Any]
    created_at: datetime


class AgentPerformanceMetricRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    agent_id: int
    agent_code: str
    executions_total: int
    executions_completed: int
    executions_failed: int
    success_rate: float
    failure_rate: float
    avg_duration_ms: int | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    recommendations_generated: int
    recommendations_reviewed: int
    recommendations_accepted: int
    recommendations_dismissed: int
    created_at: datetime


class WorkflowPerformanceMetricRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    workflow_id: int
    workflow_code: str
    executions_total: int
    executions_completed: int
    executions_failed: int
    success_rate: float
    failure_rate: float
    avg_duration_ms: int | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    created_at: datetime


class RecommendationOutcomeMetricRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    snapshot_id: int
    recommendation_type: str
    recommendations_total: int
    reviewed_total: int
    accepted_total: int
    dismissed_total: int
    acceptance_rate: float
    dismissal_rate: float
    avg_confidence_score: float
    avg_opportunity_score: float
    avg_priority_score: float
    created_at: datetime


class AgentMetricSnapshotDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: AgentMetricSnapshotRead
    agent_metrics: list[AgentPerformanceMetricRead]
    workflow_metrics: list[WorkflowPerformanceMetricRead]
    recommendation_metrics: list[RecommendationOutcomeMetricRead]


class AgentAnalyticsSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_snapshot: AgentMetricSnapshotRead | None
    summary_json: dict[str, Any]
    agent_metric_count: int
    workflow_metric_count: int
    recommendation_metric_count: int


class AgentMetricSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentMetricSnapshotRead]
    total_items: int
    limit: int
    offset: int


class AgentPerformanceMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentPerformanceMetricRead]
    total_items: int
    limit: int
    offset: int


class WorkflowPerformanceMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowPerformanceMetricRead]
    total_items: int
    limit: int
    offset: int


class RecommendationOutcomeMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecommendationOutcomeMetricRead]
    total_items: int
    limit: int
    offset: int
