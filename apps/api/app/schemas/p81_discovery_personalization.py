"""P81-02 personalized discovery, watchlists, alerts, future pull list."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.p81_discovery import P81DiscoveryOpportunityRead
from app.schemas.p77_personalization import P77PersonalizationAdjustmentRead

PersonalizedCategory = Literal["MUST_BUY", "HIGH_PRIORITY", "WATCH", "LOW_PRIORITY", "IGNORE"]
AlertPriority = Literal["CRITICAL", "HIGH", "NORMAL", "LOW"]
WatchlistType = Literal["PUBLISHER", "CHARACTER", "CREATOR", "SERIES"]


class P81PersonalizedOpportunityRead(BaseModel):
    opportunity: P81DiscoveryOpportunityRead
    discovery_score: float
    personalized_score: float
    collector_adjustment: float
    priority_category: PersonalizedCategory
    adjustments: list[P77PersonalizationAdjustmentRead] = Field(default_factory=list)
    personalization_reasons: list[str] = Field(default_factory=list)
    recommendation_action: str = "WATCH"
    recommendation_quantity: int = 0
    recommendation_score: float | None = None


class P81PersonalizedDiscoveryListResponse(BaseModel):
    items: list[P81PersonalizedOpportunityRead]
    total_items: int
    limit: int
    offset: int


class P81DiscoveryWatchlistRead(BaseModel):
    id: int
    watchlist_type: WatchlistType
    label: str
    auto_managed: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class P81DiscoveryWatchlistCreate(BaseModel):
    watchlist_type: WatchlistType
    label: str = Field(min_length=1, max_length=200)


class P81DiscoveryWatchlistUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    active: bool | None = None


class P81DiscoveryWatchlistListResponse(BaseModel):
    items: list[P81DiscoveryWatchlistRead]
    total_items: int


class P81DiscoveryAlertRead(BaseModel):
    id: int
    opportunity_id: int
    alert_type: str
    priority: AlertPriority
    title: str
    message: str
    status: str
    personalized_score: float
    created_at: datetime
    updated_at: datetime


class P81DiscoveryAlertUpdate(BaseModel):
    status: Literal["ACTIVE", "READ", "DISMISSED"] | None = None


class P81DiscoveryAlertListResponse(BaseModel):
    items: list[P81DiscoveryAlertRead]
    total_items: int
    limit: int
    offset: int


class P81FuturePullListItemRead(BaseModel):
    id: int
    opportunity_id: int
    title: str
    series_name: str
    issue_number: str
    pipeline_status: str
    watch_level: str
    recommendation_action: str
    recommendation_quantity: int
    personalized_score: float
    priority_category: PersonalizedCategory
    release_date: date | None = None
    foc_date: date | None = None
    updated_at: datetime


class P81FuturePullListResponse(BaseModel):
    items: list[P81FuturePullListItemRead]
    total_items: int
    limit: int
    offset: int


class P81FocOpportunityRead(BaseModel):
    opportunity_id: int
    title: str
    foc_date: date
    release_date: date | None = None
    personalized_score: float


class P81PersonalizedDiscoveryDashboardRead(BaseModel):
    must_buy: list[P81PersonalizedOpportunityRead] = Field(default_factory=list)
    high_priority: list[P81PersonalizedOpportunityRead] = Field(default_factory=list)
    watch: list[P81PersonalizedOpportunityRead] = Field(default_factory=list)
    future_pull_list: list[P81FuturePullListItemRead] = Field(default_factory=list)
    watchlists: list[P81DiscoveryWatchlistRead] = Field(default_factory=list)
    active_alerts: list[P81DiscoveryAlertRead] = Field(default_factory=list)
    upcoming_foc: list[P81FocOpportunityRead] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
