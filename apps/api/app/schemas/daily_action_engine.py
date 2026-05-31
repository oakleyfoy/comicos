from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyCollectorActionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    action_type: str
    priority_score: float
    confidence_score: float
    due_date: date | None = None
    title: str
    rationale: str
    source_recommendation_id: int | None = None
    source_systems: list[str] = Field(default_factory=list)
    created_at: datetime


class DailyActionSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_actions: int
    critical_actions: int
    preorder_actions: int
    acquisition_actions: int
    grading_actions: int
    sell_actions: int
    rebalance_actions: int
    watch_actions: int


class DailyActionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DailyCollectorActionRead]
    total_items: int
    limit: int
    offset: int
