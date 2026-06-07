"""P89-02 Market Pricing API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

P89PricingConfidence = Literal["HIGH", "MEDIUM", "LOW"]
P89SalesVelocity = Literal["VERY_FAST", "FAST", "NORMAL", "SLOW", "VERY_SLOW"]
P89Trend = Literal["UP", "FLAT", "DOWN"]


class P89MarketPriceSnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    series: str
    issue_number: str
    variant: str = ""
    display_title: str = ""
    quick_sale_price: float
    market_price: float
    premium_price: float
    pricing_confidence: P89PricingConfidence
    sales_velocity: P89SalesVelocity
    sales_velocity_label: str = ""
    listing_count: int
    sold_count: int
    price_low: float
    price_high: float
    price_average: float
    trend_direction: P89Trend
    snapshot_date: str
    created_at: str | None = None


class P89MarketPricingDashboardRead(BaseModel):
    highest_value_books: list[P89MarketPriceSnapshotRead] = Field(default_factory=list)
    fastest_selling_books: list[P89MarketPriceSnapshotRead] = Field(default_factory=list)
    largest_price_increases: list[P89MarketPriceSnapshotRead] = Field(default_factory=list)
    largest_price_decreases: list[P89MarketPriceSnapshotRead] = Field(default_factory=list)
    highest_confidence_pricing: list[P89MarketPriceSnapshotRead] = Field(default_factory=list)


class P89MarketPricingPortfolioTotalsRead(BaseModel):
    quick_liquidation_total: float
    market_value_total: float
    premium_value_total: float


class P89MarketPricingGenerateResponse(BaseModel):
    snapshots_created: int
    updated: int = 0
    high_confidence: int
    medium_confidence: int
    low_confidence: int
