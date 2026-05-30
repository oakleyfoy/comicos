from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentDashboardSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_agents: int
    enabled_agents: int
    total_workflows: int
    enabled_workflows: int
    active_executions: int
    total_research_snapshots: int
    total_recommendations: int
    recommendations_awaiting_review: int


class AgentHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: int
    agent_code: str
    agent_name: str
    enabled: bool
    health_status: str
    execution_count: int
    success_count: int
    failure_count: int
    success_rate: float
    average_duration_ms: int | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None


class WorkflowHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: int
    workflow_code: str
    workflow_name: str
    enabled: bool
    health_status: str
    execution_count: int
    success_count: int
    failure_count: int
    success_rate: float
    average_duration_ms: int | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None


class RecentExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: int
    execution_uuid: str
    agent_id: int
    agent_code: str
    agent_name: str
    workflow_execution_id: int | None
    workflow_id: int | None
    workflow_code: str | None
    workflow_name: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    trigger_source: str


class RecommendationQueueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: int
    recommendation_uuid: str
    recommendation_type: str
    title: str
    inventory_title: str
    status: str
    confidence_score: float
    opportunity_score: float
    priority_score: float
    created_at: datetime
    agent_execution_id: int


class AgentHealthListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentHealthRead]
    total_items: int
    limit: int
    offset: int


class WorkflowHealthListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowHealthRead]
    total_items: int
    limit: int
    offset: int


class RecentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecentExecutionRead]
    total_items: int
    limit: int
    offset: int


class RecommendationQueueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecommendationQueueRead]
    total_items: int
    limit: int
    offset: int


class AgentDashboardHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agents: list[AgentHealthRead]
    workflows: list[WorkflowHealthRead]
