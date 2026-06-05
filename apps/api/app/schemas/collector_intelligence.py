"""P62 collector intelligence API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class FOCAlertItemRead(BaseModel):
    id: int
    owner_id: int
    release_issue_id: int
    title: str
    publisher: str
    foc_date: date | None = None
    release_date: date | None = None
    recommendation_score: float
    demand_score: float
    velocity_score: float
    spec_score: float
    urgency_score: float
    alert_reason: str
    suggested_quantity: int
    status: str


class FOCAlertListRead(BaseModel):
    snapshot_id: int | None = None
    items: list[FOCAlertItemRead] = Field(default_factory=list)
    total_items: int = 0


class FOCBuildResultRead(BaseModel):
    snapshot_id: int
    total_items: int


class PullForecastItemRead(BaseModel):
    id: int
    series_name: str
    title: str
    release_issue_id: int | None = None
    confidence: str
    explanation: str
    reasons_json: dict = Field(default_factory=dict)


class PullForecastListRead(BaseModel):
    forecast_id: int | None = None
    items: list[PullForecastItemRead] = Field(default_factory=list)
    total_items: int = 0


class PullForecastBuildResultRead(BaseModel):
    forecast_id: int
    total_items: int


class AutoWatchlistItemRead(BaseModel):
    id: int
    title: str
    release_issue_id: int | None = None
    inclusion_reason: str


class AutoWatchlistRead(BaseModel):
    id: int
    watchlist_type: str
    generated_at: datetime
    item_count: int
    items: list[AutoWatchlistItemRead] = Field(default_factory=list)


class AutoWatchlistBundleRead(BaseModel):
    watchlists: list[AutoWatchlistRead] = Field(default_factory=list)


class AutoWatchlistBuildResultRead(BaseModel):
    watchlist_count: int


class CollectorComponentCertificationRead(BaseModel):
    component: str
    certified: bool
    status: str
    summary: str
    notes: list[str] = Field(default_factory=list)
    checked_at: str


class CollectorPlatformCertificationRead(BaseModel):
    platform_ready: bool
    foc: dict = Field(default_factory=dict)
    pull_forecast: dict = Field(default_factory=dict)
    auto_watchlists: dict = Field(default_factory=dict)
    checked_at: str


class CollectorPipelineRead(BaseModel):
    steps: dict[str, str] = Field(default_factory=dict)
    certification: CollectorPlatformCertificationRead
