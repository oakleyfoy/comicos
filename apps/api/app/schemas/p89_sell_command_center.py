"""P89-05 Sell Command Center schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SellCommandCenterKpiRead(BaseModel):
    sell_now_count: int = 0
    grade_first_count: int = 0
    drafts_awaiting_review: int = 0
    active_listings: int = 0
    sold_this_month: int = 0
    estimated_net_profit: float = 0.0


class SellCommandCenterQuickActionRead(BaseModel):
    label: str
    route: str
    action_type: str


class SellCommandCenterActionRead(BaseModel):
    rank: int
    title: str
    detail: str
    action_label: str
    route: str
    urgency_score: float = 0.0


class SellCommandCenterCandidateRead(BaseModel):
    sell_candidate_id: int
    inventory_copy_id: int
    comic_title: str
    recommendation: str
    sell_score: float | None = None
    hold_score: float | None = None
    grade_first_score: float | None = None
    estimated_sale_value: float = 0.0
    estimated_profit: float = 0.0
    potential_upside: float | None = None
    confidence: str = ""
    reason_summary: str = ""
    market_price: float | None = None
    trend_direction: str | None = None
    cta_label: str = "Review"
    cta_route: str = "/sell-candidates"


class SellCommandCenterDraftRead(BaseModel):
    draft_id: int
    comic_title: str
    marketplace: str
    suggested_price: float | None = None
    created_at: datetime
    cta_route: str


class SellCommandCenterActiveListingRead(BaseModel):
    listing_id: int
    comic_title: str
    marketplace: str
    asking_price: float | None = None
    minimum_price: float | None = None
    listed_at: datetime | None = None
    days_listed: int | None = None
    needs_review: bool = False
    cta_route: str


class SellCommandCenterSoldRead(BaseModel):
    listing_id: int
    comic_title: str
    sale_price: float | None = None
    net_profit: float | None = None
    profit_known: bool = True
    sold_at: datetime | None = None
    cta_route: str


class SellCommandCenterStaleRead(BaseModel):
    listing_id: int | None = None
    draft_id: int | None = None
    comic_title: str
    status: str
    marketplace: str = ""
    reason: str
    cta_route: str


class SellCommandCenterProfitSummaryRead(BaseModel):
    period_label: str = "Current month"
    gross_sales: float = 0.0
    fees: float = 0.0
    shipping_costs: float = 0.0
    net_profit: float = 0.0
    average_profit_per_sale: float = 0.0
    sold_count: int = 0


class SellCommandCenterBriefingSummaryRead(BaseModel):
    top_sell_candidate: str | None = None
    top_grade_first_candidate: str | None = None
    drafts_awaiting_review: int = 0
    active_listings: int = 0
    sold_this_month: int = 0
    net_profit_this_month: float = 0.0


class SellCommandCenterRead(BaseModel):
    status: str = "OK"
    kpis: SellCommandCenterKpiRead
    daily_actions: list[SellCommandCenterActionRead] = Field(default_factory=list)
    sell_now: list[SellCommandCenterCandidateRead] = Field(default_factory=list)
    grade_first: list[SellCommandCenterCandidateRead] = Field(default_factory=list)
    hold_or_monitor: list[SellCommandCenterCandidateRead] = Field(default_factory=list)
    drafts_needing_review: list[SellCommandCenterDraftRead] = Field(default_factory=list)
    active_listings: list[SellCommandCenterActiveListingRead] = Field(default_factory=list)
    sold_recently: list[SellCommandCenterSoldRead] = Field(default_factory=list)
    expired_or_stale: list[SellCommandCenterStaleRead] = Field(default_factory=list)
    profit_summary: SellCommandCenterProfitSummaryRead = Field(default_factory=SellCommandCenterProfitSummaryRead)
    quick_actions: list[SellCommandCenterQuickActionRead] = Field(default_factory=list)
    briefing_summary: SellCommandCenterBriefingSummaryRead = Field(default_factory=SellCommandCenterBriefingSummaryRead)
    generated_at: datetime
