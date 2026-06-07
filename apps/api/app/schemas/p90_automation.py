"""P90 Automation & Alerts schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P90CollectorAlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    priority_score: float
    title: str
    summary: str
    source_system: str
    entity_type: str
    entity_id: int
    status: str
    confidence: str
    reason: str
    action_route: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    dismissed_at: datetime | None = None


class P90CollectorAlertListResponse(BaseModel):
    items: list[P90CollectorAlertRead] = Field(default_factory=list)
    total: int = 0


class P90CollectorAlertUpdate(BaseModel):
    status: str


class P90ActionQueueItemRead(BaseModel):
    rank: int
    title: str
    detail: str
    action_type: str
    priority_score: float
    confidence: str
    action_route: str
    alert_id: int


class P90AutomationSummaryRead(BaseModel):
    status: str = "OK"
    buy_alerts_count: int = 0
    sell_alerts_count: int = 0
    grade_alerts_count: int = 0
    collection_gap_count: int = 0
    release_alerts_count: int = 0
    new_alerts_count: int = 0
    todays_actions: list[P90ActionQueueItemRead] = Field(default_factory=list)
    briefing_summary: dict = Field(default_factory=dict)
    generated_at: datetime


class P90AutomationDashboardRead(BaseModel):
    status: str = "OK"
    todays_actions: list[P90ActionQueueItemRead] = Field(default_factory=list)
    buy_alerts: list[P90CollectorAlertRead] = Field(default_factory=list)
    sell_alerts: list[P90CollectorAlertRead] = Field(default_factory=list)
    grade_alerts: list[P90CollectorAlertRead] = Field(default_factory=list)
    collection_gaps: list[P90CollectorAlertRead] = Field(default_factory=list)
    release_alerts: list[P90CollectorAlertRead] = Field(default_factory=list)
    generated_at: datetime


class P90AutomationRunSummaryRead(BaseModel):
    alerts_created: int
    alerts_updated: int
    alerts_dismissed: int
    actions_generated: int
    status: str
    dry_run: bool
