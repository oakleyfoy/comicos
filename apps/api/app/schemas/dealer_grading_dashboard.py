"""P37-08 dealer grading dashboard API contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DealerGradingDashboardAlertType = Literal[
    "NEGATIVE_ROI",
    "HIGH_RISK",
    "LOW_CONFIDENCE",
    "SUBMISSION_DELAY",
    "RECONCILIATION_FAILURE",
    "WEAK_LIQUIDITY",
    "MISSING_EVIDENCE",
]

DealerGradingDashboardSeverity = Literal["info", "warning", "critical"]

DealerGradingDashboardFeedEventType = Literal[
    "CANDIDATE_CREATED",
    "RECOMMENDATION_GENERATED",
    "SUBMISSION_BATCH_CREATED",
    "SUBMISSION_SHIPPED",
    "GRADES_RETURNED",
    "RECONCILIATION_COMPLETED",
    "HIGH_RISK_DETECTED",
    "ELITE_OPPORTUNITY_DETECTED",
]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class DealerGradingDashboardGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = Field(default=None, description="Defaults to UTC calendar date when omitted.")
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)

    _trim_replay_key = field_validator("replay_key", mode="before")(_trim)


class DealerGradingDashboardSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_key: str | None = None
    active_candidate_count: int
    ready_for_submission_count: int
    submitted_candidate_count: int
    graded_candidate_count: int
    elite_recommendation_count: int
    high_risk_candidate_count: int
    low_confidence_candidate_count: int
    average_estimated_roi: Decimal | None = None
    average_risk_adjusted_roi: Decimal | None = None
    active_submission_batch_count: int
    grading_pipeline_value: Decimal | None = None
    estimated_total_submission_cost: Decimal | None = None
    expected_total_profit: Decimal | None = None
    checksum: str
    snapshot_date: date
    created_at: datetime


class DealerGradingDashboardGetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: DealerGradingDashboardSnapshotRead | None


class DealerGradingDashboardGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: DealerGradingDashboardSnapshotRead


class DealerGradingDashboardMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dashboard_snapshot_id: int
    metric_key: str
    metric_value_decimal: Decimal | None = None
    metric_value_text: str | None = None
    metric_metadata_json: dict | None = None
    created_at: datetime


class DealerGradingDashboardAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    dashboard_snapshot_id: int
    alert_type: DealerGradingDashboardAlertType | str
    severity: DealerGradingDashboardSeverity | str
    source_candidate_id: int | None = None
    source_submission_batch_id: int | None = None
    source_recommendation_id: int | None = None
    message: str
    acknowledged_at: datetime | None = None
    created_at: datetime


class DealerGradingDashboardFeedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    dashboard_snapshot_id: int | None = None
    event_type: DealerGradingDashboardFeedEventType | str
    source_id: int | None = None
    summary: str
    metadata_json: dict | None = None
    created_at: datetime


class DealerGradingDashboardMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerGradingDashboardMetricRead]
    total_items: int
    limit: int
    offset: int


class DealerGradingDashboardAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerGradingDashboardAlertRead]
    total_items: int
    limit: int
    offset: int


class DealerGradingDashboardFeedListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DealerGradingDashboardFeedEventRead]
    total_items: int
    limit: int
    offset: int
