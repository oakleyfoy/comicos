from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PullListAutomationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    owners_processed: int
    releases_processed: int
    decisions_created: int
    actions_generated: int
    runtime_ms: int
    error_message: str = ""


class PullListAutomationRunListResponse(BaseModel):
    items: list[PullListAutomationRunRead]
    total_items: int
    limit: int
    offset: int


class PullListAutomationRunTriggerResponse(BaseModel):
    run: PullListAutomationRunRead


class PullListAutomationHealthRead(BaseModel):
    last_run: datetime | None = None
    run_status: str = "NEVER_RUN"
    runtime_ms: int = 0
    decision_count: int = 0
    action_count: int = 0
    last_run_decisions_created: int = 0
    last_run_actions_generated: int = 0


class PullListAutomationOpsPanelRead(BaseModel):
    last_run: datetime | None = None
    status: str = "NEVER_RUN"
    runtime_ms: int = 0
    decisions_generated: int = 0
    actions_generated: int = 0
