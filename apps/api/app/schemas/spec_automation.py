from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpecAutomationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    inputs_processed: int
    baseline_scores_created: int
    ai_evaluations_created: int
    top_picks_created: int
    runtime_ms: int
    error_message: str | None = None


class SpecAutomationRunListRead(BaseModel):
    items: list[SpecAutomationRunRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class SpecAutomationRunTriggerResponse(BaseModel):
    run: SpecAutomationRunRead


class SpecAutomationOpsPanelRead(BaseModel):
    last_run: datetime | None = None
    status: str = "NEVER_RUN"
    runtime_ms: int = 0
    inputs_processed: int = 0
    baseline_scores_created: int = 0
    ai_evaluations_created: int = 0
    top_picks_created: int = 0
