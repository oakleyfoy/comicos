from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationAnalyticsType = Literal[
    "QUEUE_ANALYTICS",
    "WORKER_ANALYTICS",
    "WORKFLOW_ANALYTICS",
    "RECOVERY_ANALYTICS",
    "REPLAY_ANALYTICS",
    "BATCH_ANALYTICS",
    "NOTIFICATION_ANALYTICS",
    "SYSTEM_ANALYTICS",
]
AutomationAnalyticsStatus = Literal["HEALTHY", "WARNING", "DEGRADED", "CRITICAL"]
AutomationAnalyticsMetricCategory = Literal["THROUGHPUT", "LATENCY", "FAILURE", "RECOVERY", "REPLAY", "UTILIZATION", "STORAGE", "SYSTEM"]
AutomationAnalyticsMetricStatus = Literal["NORMAL", "WARNING", "CRITICAL"]
AutomationAnalyticsTrendType = Literal[
    "QUEUE_GROWTH",
    "FAILURE_RATE",
    "RECOVERY_RATE",
    "REPLAY_WARNING_RATE",
    "WORKER_UTILIZATION",
    "BATCH_GROWTH",
    "ALERT_VOLUME",
    "WORKFLOW_THROUGHPUT",
]
AutomationAnalyticsTrendDirection = Literal["UP", "DOWN", "STABLE"]
AutomationAnalyticsComparisonType = Literal[
    "DAY_OVER_DAY",
    "WEEK_OVER_WEEK",
    "SNAPSHOT_COMPARE",
    "REPLAY_COMPARE",
    "FAILURE_COMPARE",
    "UTILIZATION_COMPARE",
]
AutomationAnalyticsSeverity = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


class AutomationAnalyticsSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    analytics_type: AutomationAnalyticsType | str
    analytics_scope: str = Field(min_length=1, max_length=80)
    replay_key: str = Field(min_length=1, max_length=120)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AutomationAnalyticsSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    organization_id: int | None = None
    snapshot_key: str
    analytics_type: str
    analytics_scope: str
    analytics_status: str
    replay_safe: bool
    deterministic_ordering_enabled: bool
    snapshot_checksum: str
    snapshot_manifest_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    metric_key: str
    metric_category: str
    metric_value: str
    metric_delta: str | None = None
    metric_status: str
    metric_rank: int
    metric_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsTrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    trend_key: str
    trend_type: str
    trend_direction: str
    historical_window: int
    trend_value: str
    trend_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    comparison_key: str
    comparison_type: str
    baseline_snapshot_id: int | None = None
    comparison_result_json: dict[str, Any]
    comparison_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    issue_type: str
    severity: AutomationAnalyticsSeverity | str
    issue_message: str
    issue_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int | None = None
    comparison_id: int | None = None
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    event_message: str
    event_checksum: str
    metadata_json: dict[str, Any]
    created_at: datetime


class AutomationAnalyticsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    total_items: int
    limit: int
    offset: int
    replay_drift_count: int = 0
    failure_warning_count: int = 0
    utilization_warning_count: int = 0


class AutomationAnalyticsSystemIntelligenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analytics_status: str
    queue_throughput: int
    worker_utilization: str
    failure_rate: str
    replay_warning_trend_count: int
    dead_letter_growth: int
    workflow_throughput: int
    notification_delivery_rate: str
    batch_completion_rate: str
    latest_snapshot_id: int | None = None
    latest_snapshot_checksum: str | None = None
