"""P90-02 FMV V2 API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class P90FmvSnapshotRead(BaseModel):
    id: int
    series: str
    issue_number: str
    variant: str
    quick_sale_value: float
    market_value: float
    premium_value: float
    valuation_confidence: str
    trend_direction: str
    trend_score: float
    sales_velocity: str
    listing_count: int
    marketplace_count: int
    valuation_source: str
    snapshot_date: date
    created_at: datetime


class P90FmvV2CopyRead(BaseModel):
    inventory_copy_id: int
    legacy_fmv: float | None = None
    quick_sale_value: float
    market_value: float
    premium_value: float
    valuation_confidence: str
    trend_direction: str
    trend_score: float
    sales_velocity: str


class P90FmvIntelligenceDashboardRead(BaseModel):
    status: str = "OK"
    portfolio: dict = Field(default_factory=dict)
    highest_value: list[P90FmvSnapshotRead] = Field(default_factory=list)
    largest_movers: list[P90FmvSnapshotRead] = Field(default_factory=list)
    strongest_uptrends: list[P90FmvSnapshotRead] = Field(default_factory=list)
    strongest_downtrends: list[P90FmvSnapshotRead] = Field(default_factory=list)
    highest_confidence: list[P90FmvSnapshotRead] = Field(default_factory=list)
    lowest_confidence: list[P90FmvSnapshotRead] = Field(default_factory=list)
    generated_at: datetime


class P90FmvDiagnosticsRead(BaseModel):
    snapshot_count: int
    identity_coverage: int
    confidence_distribution: dict[str, int]
    source_distribution: dict[str, int]
    trend_distribution: dict[str, int]
    generated_at: datetime
