from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int = Field(ge=1)
    agent_definition_id: int = Field(ge=1)
    step_name: str = Field(min_length=1, max_length=160)
    step_code: str = Field(min_length=1, max_length=80)
    required_success: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1)


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    workflow_id: int
    step_order: int
    agent_definition_id: int
    step_name: str
    step_code: str
    required_success: bool
    timeout_seconds: int | None


class WorkflowDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_code: str = Field(min_length=1, max_length=80)
    workflow_name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    enabled: bool = False
    schedule_enabled: bool = False
    cron_expression: str | None = Field(default=None, max_length=120)
    next_run_at: datetime | None = None
    steps: list[WorkflowStepCreate] = Field(default_factory=list)


class WorkflowDefinitionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    workflow_code: str
    workflow_name: str
    description: str
    enabled: bool
    schedule_enabled: bool
    cron_expression: str | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepRead]


class WorkflowExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    workflow_id: int
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    triggered_by: str
    trigger_source: str


class WorkflowStepExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    workflow_execution_id: int
    workflow_step_id: int
    agent_execution_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class WorkflowExecutionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: WorkflowDefinitionRead
    execution: WorkflowExecutionRead
    step_executions: list[WorkflowStepExecutionRead]


class WorkflowDefinitionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowDefinitionRead]
    total_items: int
    limit: int
    offset: int


class WorkflowExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WorkflowExecutionRead]
    total_items: int
    limit: int
    offset: int
