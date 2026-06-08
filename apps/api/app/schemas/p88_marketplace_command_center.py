"""P88-05 Marketplace Command Center API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MarketplaceCommandCenterKpiRead(BaseModel):
    active_opportunities: int = 0
    marketplace_alerts: int = 0
    price_drops: int = 0
    watchlist_matches: int = 0
    collection_gaps: int = 0
    upcoming_releases: int = 0


class MarketplaceCommandCenterQuickActionRead(BaseModel):
    label: str
    route: str
    action_type: str


class BestDealTodayRead(BaseModel):
    opportunity_id: int
    title: str
    marketplace: str | None = None
    marketplace_name: str | None = None
    price: float
    fmv: float
    upside_percent: float | None = None
    savings_vs_highest: float | None = None
    opportunity_score: float
    recommendation: str
    has_verified_listing: bool = False
    action_url: str = ""
    action_url_type: str = "OPPORTUNITY_DETAIL"
    recommendation_type: str = ""


class PriceDropRead(BaseModel):
    opportunity_id: int | None = None
    listing_id: int | None = None
    title: str
    marketplace: str
    marketplace_name: str
    old_price: float
    new_price: float
    drop_percent: float


class CollectionGapFeedRead(BaseModel):
    gap_id: int
    title: str
    reason: str
    gap_type: str
    priority: str


class WatchlistMatchRead(BaseModel):
    alert_id: int
    saved_search_name: str
    title: str
    marketplace: str | None = None
    marketplace_name: str | None = None
    price: float | None = None
    message: str
    alert_type: str


class UpcomingReleaseBuyRead(BaseModel):
    item_id: int
    title: str
    release_date: date | None = None
    foc_date: date | None = None
    recommendation: str
    personalized_score: float


class TopRecommendationRead(BaseModel):
    opportunity_id: int
    title: str
    cover_image_url: str = ""
    score: float
    reason_summary: str
    best_marketplace_name: str | None = None
    best_price: float | None = None
    recommendation: str


class MarketplaceActivityItemRead(BaseModel):
    activity_type: str
    title: str
    message: str
    created_at: datetime


class MarketplaceCommandCenterBriefingSummaryRead(BaseModel):
    best_deal_title: str | None = None
    largest_price_drop_title: str | None = None
    top_recommendation_title: str | None = None
    watchlist_match_title: str | None = None


class MarketplaceCommandCenterRead(BaseModel):
    status: str = "OK"
    kpis: MarketplaceCommandCenterKpiRead
    best_deals_today: list[BestDealTodayRead] = Field(default_factory=list)
    recommended_buys_today: list[BestDealTodayRead] = Field(default_factory=list)
    watchlist_opportunities_today: list[BestDealTodayRead] = Field(default_factory=list)
    price_drops: list[PriceDropRead] = Field(default_factory=list)
    collection_gaps: list[CollectionGapFeedRead] = Field(default_factory=list)
    watchlist_matches: list[WatchlistMatchRead] = Field(default_factory=list)
    upcoming_releases: list[UpcomingReleaseBuyRead] = Field(default_factory=list)
    top_recommendations: list[TopRecommendationRead] = Field(default_factory=list)
    marketplace_activity: list[MarketplaceActivityItemRead] = Field(default_factory=list)
    quick_actions: list[MarketplaceCommandCenterQuickActionRead] = Field(default_factory=list)
    briefing_summary: MarketplaceCommandCenterBriefingSummaryRead = Field(
        default_factory=MarketplaceCommandCenterBriefingSummaryRead
    )
    generated_at: datetime
