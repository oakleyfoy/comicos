from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.release_intelligence import ReleaseIssueRead, ReleaseSeriesRead, ReleaseVariantRead
from app.schemas.spec_intelligence import SpecRecommendationRead


class ReleaseHorizonIssueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon: str
    issue: ReleaseIssueRead
    series: ReleaseSeriesRead


class ReleaseHorizonsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    announced: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    next_30_days: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    next_60_days: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    next_90_days: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    foc_approaching: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    releasing_soon: list[ReleaseHorizonIssueRead] = Field(default_factory=list)
    released: list[ReleaseHorizonIssueRead] = Field(default_factory=list)


class RankedOpportunityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    release_issue_id: int
    issue: ReleaseIssueRead
    series: ReleaseSeriesRead
    ranking_score: float
    score_components: dict[str, float] = Field(default_factory=dict)
    recommendation: SpecRecommendationRead | None = None


class OpportunityIntelligenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_new_opportunities: list[RankedOpportunityRead] = Field(default_factory=list)
    top_spec_opportunities: list[RankedOpportunityRead] = Field(default_factory=list)
    top_variant_opportunities: list[RankedOpportunityRead] = Field(default_factory=list)
    top_first_appearances: list[RankedOpportunityRead] = Field(default_factory=list)
    top_milestone_books: list[RankedOpportunityRead] = Field(default_factory=list)
    top_new_number_ones: list[RankedOpportunityRead] = Field(default_factory=list)


class FutureBuyQueueItemRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_window: str
    buy_category: str
    release_issue_id: int
    issue: ReleaseIssueRead
    series: ReleaseSeriesRead
    ranking_score: float


class FutureBuyQueueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_30_days: list[FutureBuyQueueItemRead] = Field(default_factory=list)
    next_60_days: list[FutureBuyQueueItemRead] = Field(default_factory=list)
    next_90_days: list[FutureBuyQueueItemRead] = Field(default_factory=list)


class ContinueRunPlanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_type: str
    publisher: str
    series_name: str
    latest_issue_owned: str | None = None
    target_issue_number: str
    release_issue_id: int
    issue: ReleaseIssueRead
    series: ReleaseSeriesRead


class BudgetCategorySpendRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_buy: float
    strong_buy: float
    watch: float


class BudgetForecastRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days_30: BudgetCategorySpendRead
    days_60: BudgetCategorySpendRead
    days_90: BudgetCategorySpendRead
    expected_spend_total_30: float
    expected_spend_total_60: float
    expected_spend_total_90: float


class ReleaseOpportunityDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_announcements: list[ReleaseHorizonIssueRead]
    next_30_days: list[ReleaseHorizonIssueRead]
    next_60_days: list[ReleaseHorizonIssueRead]
    next_90_days: list[ReleaseHorizonIssueRead]
    continue_run_alerts: list[ContinueRunPlanRead]
    start_following_alerts: list[ContinueRunPlanRead] = Field(default_factory=list)
    new_opportunity_alerts: list[ContinueRunPlanRead] = Field(default_factory=list)
    top_new_number_ones: list[RankedOpportunityRead]
    top_first_appearances: list[RankedOpportunityRead]
    top_milestone_issues: list[RankedOpportunityRead]
    top_variants: list[RankedOpportunityRead]
    top_spec_opportunities: list[RankedOpportunityRead]
    future_buy_queue: FutureBuyQueueRead
    budget_forecast: BudgetForecastRead
    variant_count: int = 0
    ratio_variant_count: int = 0
    cover_variant_count: int = 0
    top_ratio_variants: list[ReleaseVariantRead] = Field(default_factory=list)
    top_new_variants: list[ReleaseVariantRead] = Field(default_factory=list)


class ContinueRunPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ContinueRunPlanRead]
