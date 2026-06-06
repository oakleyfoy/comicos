"""P81-03 discovery analytics and certification schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class P81DiscoveryActivityRead(BaseModel):
    opportunities_discovered: int
    opportunities_published: int
    opportunities_viewed: int
    opportunities_saved: int
    opportunities_purchased: int


class P81DiscoveryCategoryPerformanceRead(BaseModel):
    category: str
    detected: int
    purchased: int
    conversion_rate_pct: float


class P81DiscoveryAlertPerformanceRead(BaseModel):
    alerts_sent: int
    alerts_opened: int
    alerts_clicked: int
    alerts_converted: int
    by_type: dict[str, int] = Field(default_factory=dict)


class P81DiscoveryWatchlistPerformanceRead(BaseModel):
    label: str
    watchlist_type: str
    matches: int
    purchases: int
    roi_pct: float


class P81FuturePullAnalyticsRead(BaseModel):
    recommendations: int
    purchased: int
    skipped: int
    accuracy_pct: float


class P81PersonalizationImpactRead(BaseModel):
    opportunities_evaluated: int
    opportunities_adjusted: int
    adjustment_rate_pct: float
    adjustment_types: dict[str, int] = Field(default_factory=dict)


class P81DiscoveryRoiRead(BaseModel):
    portfolio_roi_pct: float
    average_fmv_gain_pct: float
    highlights: list[dict] = Field(default_factory=list)


class P81DiscoveryAnalyticsRead(BaseModel):
    activity: P81DiscoveryActivityRead
    snapshot_id: int | None = None


class P81DiscoveryOpportunityAnalyticsRead(BaseModel):
    categories: list[P81DiscoveryCategoryPerformanceRead]
    snapshot_id: int | None = None


class P81DiscoveryAlertAnalyticsRead(BaseModel):
    performance: P81DiscoveryAlertPerformanceRead
    snapshot_id: int | None = None


class P81DiscoveryRoiAnalyticsRead(BaseModel):
    roi: P81DiscoveryRoiRead
    snapshot_id: int | None = None


class P81DiscoveryAnalyticsDashboardRead(BaseModel):
    activity: P81DiscoveryActivityRead
    opportunity_performance: list[P81DiscoveryCategoryPerformanceRead]
    alert_performance: P81DiscoveryAlertPerformanceRead
    watchlist_performance: list[P81DiscoveryWatchlistPerformanceRead]
    future_pull: P81FuturePullAnalyticsRead
    discovery_roi: P81DiscoveryRoiRead
    personalization_impact: P81PersonalizationImpactRead
    snapshot_ids: dict[str, int | None] = Field(default_factory=dict)


class P81DiscoveryCertificationCheckRead(BaseModel):
    category: str
    component: str
    passed: bool
    detail: str = ""


class P81DiscoveryCertificationRead(BaseModel):
    title: str
    status: str
    approved_for_production: bool
    checks_passed: int
    warnings: int
    failures: int
    platform_readiness_percent: float
    production_checklist: list[dict[str, str]] = Field(default_factory=list)
    checks: list[P81DiscoveryCertificationCheckRead] = Field(default_factory=list)
