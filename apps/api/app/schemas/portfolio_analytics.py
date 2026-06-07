"""P67 Portfolio Analytics API schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class P67PortfolioPerformanceSnapshotRead(_Orm):
    id: int
    owner_user_id: int
    snapshot_date: date
    generated_at: datetime
    total_cost_basis: float
    total_estimated_value: float
    total_unrealized_gain: float
    total_unrealized_gain_pct: float
    total_realized_gain: float
    total_realized_gain_pct: float
    average_roi_pct: float
    portfolio_cagr_pct: float | None = None
    best_performer_title: str = ""
    worst_performer_title: str = ""
    largest_position_title: str = ""
    metadata_json: dict = Field(default_factory=dict)


class P67PortfolioPerformanceItemRead(_Orm):
    id: int
    title: str
    publisher: str
    series: str
    issue_number: str
    cost_basis: float
    estimated_value: float
    unrealized_gain: float
    unrealized_gain_pct: float
    realized_gain: float
    realized_gain_pct: float
    roi_pct: float


class P67PortfolioPerformanceListRead(BaseModel):
    snapshot: P67PortfolioPerformanceSnapshotRead | None = None
    items: list[P67PortfolioPerformanceItemRead] = Field(default_factory=list)


class P67CollectionAnalyticsLatestRead(BaseModel):
    status: str = "OK"
    message: str = ""
    total_holdings: int = 0
    concentration_score: float = 0.0
    metadata_json: dict = Field(default_factory=dict)


class P67InvestorDashboardLatestRead(BaseModel):
    status: str = "OK"
    message: str = ""
    collection_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_gain: float = 0.0
    realized_gain: float = 0.0
    portfolio_health_score: float = 0.0
    cards_json: dict = Field(default_factory=dict)


class P67CollectionAnalyticsSnapshotRead(_Orm):
    id: int
    owner_user_id: int
    snapshot_date: date
    generated_at: datetime
    total_holdings: int
    concentration_score: float
    metadata_json: dict = Field(default_factory=dict)


class P67RecommendationPerformanceSnapshotRead(_Orm):
    id: int
    owner_user_id: int
    snapshot_date: date
    generated_at: datetime
    total_tracked: int
    hit_rate_pct: float
    average_return_pct: float
    recommendation_roi_pct: float
    confidence_accuracy_pct: float
    best_recommendation_title: str = ""
    worst_recommendation_title: str = ""
    metadata_json: dict = Field(default_factory=dict)


class P67RecommendationPerformanceItemRead(_Orm):
    id: int
    title: str
    recommendation_type: str
    outcome: str
    return_pct: float
    held: bool
    purchased: bool
    priority_score: float
    confidence_score: float


class P67RecommendationPerformanceListRead(BaseModel):
    snapshot: P67RecommendationPerformanceSnapshotRead | None = None
    items: list[P67RecommendationPerformanceItemRead] = Field(default_factory=list)


class P67GradingOpportunitySnapshotRead(_Orm):
    id: int
    owner_user_id: int
    snapshot_date: date
    generated_at: datetime
    total_candidates: int
    metadata_json: dict = Field(default_factory=dict)


class P67GradingOpportunityItemRead(_Orm):
    id: int
    title: str
    estimated_grade: str
    submission_candidate_score: float
    estimated_roi_pct: float
    raw_value: float
    graded_value: float
    submission_priority: int


class P67GradingOpportunityListRead(BaseModel):
    snapshot: P67GradingOpportunitySnapshotRead | None = None
    items: list[P67GradingOpportunityItemRead] = Field(default_factory=list)


class P67InvestorDashboardSnapshotRead(_Orm):
    id: int
    owner_user_id: int
    snapshot_date: date
    generated_at: datetime
    collection_value: float
    cost_basis: float
    unrealized_gain: float
    realized_gain: float
    portfolio_health_score: float
    cards_json: dict = Field(default_factory=dict)


class P67PlatformBuildRead(BaseModel):
    status: str = "OK"
    message: str = ""
    steps: list[dict] = Field(default_factory=list)
    certification: dict = Field(default_factory=dict)


class P67CertificationRead(BaseModel):
    owner_user_id: int
    certified: bool
    checks: list[dict] = Field(default_factory=list)
    platform: str
