"""P38-07 portfolio strategy dashboard API contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PortfolioStrategyDashboardAlertType = Literal[
    "OVEREXPOSURE",
    "DEAD_CAPITAL",
    "DUPLICATE_RISK",
    "LIQUIDITY_IMBALANCE",
    "CONCENTRATION_CRITICAL",
    "WEAK_DIVERSIFICATION",
    "HIGH_RISK_HOLDING",
    "ACQUISITION_GAP",
]
PortfolioStrategyDashboardAlertSeverity = Literal["info", "warning", "critical"]
PortfolioStrategyDashboardFeedEventType = Literal[
    "PORTFOLIO_CREATED",
    "EXPOSURE_GENERATED",
    "DUPLICATE_CLUSTER_CREATED",
    "HOLD_RECOMMENDATION_CREATED",
    "SELL_RECOMMENDATION_CREATED",
    "CONCENTRATION_ALERT",
    "ACQUISITION_OPPORTUNITY",
    "LIQUIDITY_WARNING",
]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class PortfolioStrategyDashboardGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = Field(default=None, description="Defaults to the current UTC calendar date.")
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)

    _trim_replay_key = field_validator("replay_key", mode="before")(_trim)


class PortfolioStrategyDashboardSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    replay_key: str | None = None
    portfolio_count: int
    total_portfolio_value: Decimal | None = None
    total_cost_basis: Decimal | None = None
    total_realized_sales: Decimal | None = None
    diversification_score: Decimal | None = None
    liquidity_efficiency_score: Decimal | None = None
    concentration_risk_score: Decimal | None = None
    dead_capital_estimate: Decimal | None = None
    duplicate_cluster_count: int
    overexposed_category_count: int
    hold_recommendation_count: int
    sell_recommendation_count: int
    reduce_exposure_count: int
    acquisition_opportunity_count: int
    elite_acquisition_count: int
    grading_candidate_count: int
    liquid_inventory_percentage: Decimal | None = None
    illiquid_inventory_percentage: Decimal | None = None
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioStrategyDashboardMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dashboard_snapshot_id: int
    metric_key: str
    metric_value_decimal: Decimal | None = None
    metric_value_text: str | None = None
    metric_metadata_json: dict | None = None
    created_at: datetime


class PortfolioStrategyDashboardAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    alert_type: PortfolioStrategyDashboardAlertType | str
    severity: PortfolioStrategyDashboardAlertSeverity | str
    alert_replay_key: str
    source_portfolio_id: int | None = None
    source_inventory_item_id: int | None = None
    source_snapshot_id: int | None = None
    message: str
    acknowledged_at: datetime | None = None
    created_at: datetime


class PortfolioStrategyDashboardFeedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    deterministic_key: str
    dashboard_snapshot_id: int | None = None
    event_type: PortfolioStrategyDashboardFeedEventType | str
    source_id: int | None = None
    summary: str
    metadata_json: dict | None = None
    created_at: datetime


class PortfolioStrategyDashboardGetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: PortfolioStrategyDashboardSnapshotRead | None


class PortfolioStrategyDashboardGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: PortfolioStrategyDashboardSnapshotRead


class PortfolioStrategyDashboardMetricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PortfolioStrategyDashboardMetricRead]
    total_items: int
    limit: int
    offset: int


class PortfolioStrategyDashboardAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PortfolioStrategyDashboardAlertRead]
    total_items: int
    limit: int
    offset: int


class PortfolioStrategyDashboardFeedListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PortfolioStrategyDashboardFeedEventRead]
    total_items: int
    limit: int
    offset: int
