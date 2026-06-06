"""P74-02 FOC and purchase intelligence schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class P74FocWatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    foc_this_week: int
    foc_next_week: int
    foc_within_30_days: int
    foc_missed: int
    foc_unknown: int


class P74PurchaseRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    release_issue_id: int
    publisher: str
    series_name: str
    issue_number: str
    foc_date: date | None
    release_date: date | None
    foc_bucket: str
    priority_score: int
    purchase_action: str
    quantity_recommended: int
    owned_quantity: int
    ordered_quantity: int
    watchlist_match: bool
    reasoning: str


class P74PurchaseRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P74PurchaseRecommendationChangeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    release_issue_id: int
    change_kind: str
    previous_action: str
    current_action: str
    previous_quantity: int
    current_quantity: int
    reason: str
    created_at: datetime


class P74RecommendationChangeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P74PurchaseRecommendationChangeRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int = 0


class P74FocAlertSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_type: str
    title: str
    message: str


class P74FocDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int
    generated_at: datetime
    foc_watch: P74FocWatchRead
    foc_this_week: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    last_chance: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    recommended_preorders: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    quantity_changes: list[P74PurchaseRecommendationChangeRead] = Field(default_factory=list)
    recommendation_upgrades: list[P74PurchaseRecommendationChangeRead] = Field(default_factory=list)
    recommendation_downgrades: list[P74PurchaseRecommendationChangeRead] = Field(default_factory=list)
    missed_foc: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    watchlist_matches: list[P74PurchaseRecommendationRead] = Field(default_factory=list)
    alerts: list[P74FocAlertSummaryRead] = Field(default_factory=list)
