"""P65 Collector Experience API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CollectorTaskItemRead(BaseModel):
    id: int
    snapshot_id: int
    task_type: str
    status: str
    title: str
    publisher: str
    issue_number: str
    priority_score: float
    source_system: str
    source_ref_json: dict[str, Any] = Field(default_factory=dict)
    explanation: str
    action_hint: str
    updated_at: datetime | None = None


class CollectorTaskSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    generated_at: datetime | None = None
    total_items: int = 0
    items: list[CollectorTaskItemRead] = Field(default_factory=list)
    by_type: dict[str, int] = Field(default_factory=dict)


class CollectorTaskBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int
    status: str = "SUCCESS"


class CollectorTaskStatusPatch(BaseModel):
    status: str


class CollectorTaskBulkPatch(BaseModel):
    task_ids: list[int]
    status: str


class CollectorTaskHistoryEntryRead(BaseModel):
    snapshot_id: int
    generated_at: datetime
    total_items: int


class CollectorNarrativeItemRead(BaseModel):
    id: int
    narrative_kind: str
    title: str
    narrative_text: str
    signal_citations_json: list[Any] = Field(default_factory=list)


class CollectorNarrativeSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    week_start: str = ""
    briefing_markdown: str = ""
    items: list[CollectorNarrativeItemRead] = Field(default_factory=list)


class AutomationSubscriptionRead(BaseModel):
    id: int
    automation_kind: str
    delivery_type: str
    enabled: bool
    config_json: dict[str, Any] = Field(default_factory=dict)


class AutomationRunRead(BaseModel):
    id: int
    automation_kind: str
    delivery_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)


class NotificationItemRead(BaseModel):
    id: int
    notification_type: str
    status: str
    title: str
    message: str
    deep_link: str
    created_at: datetime | None = None


class NotificationSnapshotRead(BaseModel):
    snapshot_id: int | None = None
    readiness_status: str = "NOT_READY"
    unread_count: int = 0
    total_items: int = 0
    items: list[NotificationItemRead] = Field(default_factory=list)


class NotificationStatusPatch(BaseModel):
    status: str


class P65CertificationRead(BaseModel):
    certified: bool
    platform_ready: bool
    checks: dict[str, Any] = Field(default_factory=dict)
    non_mutation: dict[str, Any] = Field(default_factory=dict)


class CollectorTaskHistoryListRead(BaseModel):
    entries: list[CollectorTaskHistoryEntryRead] = Field(default_factory=list)


class CollectorBulkUpdateRead(BaseModel):
    updated: int = 0


class NarrativeBuildResultRead(BaseModel):
    snapshot_id: int
    readiness_status: str


class AutomationSubscriptionsListRead(BaseModel):
    subscriptions: list[AutomationSubscriptionRead] = Field(default_factory=list)


class AutomationRunsListRead(BaseModel):
    runs: list[AutomationRunRead] = Field(default_factory=list)


class AutomationRunAllRead(BaseModel):
    run_count: int = 0


class NotificationBuildResultRead(BaseModel):
    snapshot_id: int
    unread_count: int
    total_items: int
