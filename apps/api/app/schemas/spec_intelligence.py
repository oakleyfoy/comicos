from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.release_intelligence import ReleaseVariantRead


class SpecScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    release_issue_id: int
    score_value: float
    score_grade: str
    confidence_score: float
    score_payload_json: dict[str, object]
    created_at: datetime


class SpecRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_uuid: str
    release_issue_id: int
    recommendation_type: str
    recommendation_score: float
    confidence_score: float
    recommendation_reason: str
    created_at: datetime


class SpecRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    review_status: str
    reviewed_at: datetime
    review_notes: str


class WeeklyBuyListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    list_uuid: str
    week_start_date: date
    generated_at: datetime


class WeeklyBuyListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weekly_buy_list_id: int
    release_issue_id: int
    buy_category: str
    ranking_score: float
    created_at: datetime


class SpecAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime


class SpecRecommendationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_notes: str = ""


class WeeklyBuyListDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_buy_list: WeeklyBuyListRead
    items: list[WeeklyBuyListItemRead] = Field(default_factory=list)


class SpecScoreListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SpecScoreRead]
    total_items: int
    limit: int
    offset: int


class SpecRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SpecRecommendationRead]
    total_items: int
    limit: int
    offset: int


class WeeklyBuyListListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WeeklyBuyListDetailRead]
    total_items: int
    limit: int
    offset: int


class SpecAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SpecAgentExecutionRead]
    total_items: int
    limit: int
    offset: int


class SpecReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: SpecRecommendationRead
    review: SpecRecommendationReviewRead


class SpecScoringRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: list[SpecScoreRead]
    execution: SpecAgentExecutionRead


class SpecRecommendationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[SpecRecommendationRead]
    execution: SpecAgentExecutionRead


class WeeklyBuyListRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_buy_list: WeeklyBuyListDetailRead
    execution: SpecAgentExecutionRead


class SpecDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_spec_opportunities: list[SpecRecommendationRead]
    weekly_buy_lists: list[WeeklyBuyListDetailRead]
    new_number_one_opportunities: list[SpecRecommendationRead]
    variant_opportunities: list[SpecRecommendationRead]
    key_issue_opportunities: list[SpecRecommendationRead]
    watch_opportunities: list[SpecRecommendationRead]
    recommendation_reviews: list[SpecRecommendationReviewRead]
    agent_activity: list[SpecAgentExecutionRead]
    variant_count: int = 0
    ratio_variant_count: int = 0
    top_ratio_variants: list[ReleaseVariantRead] = Field(default_factory=list)
    upcoming_incentive_variants: list[ReleaseVariantRead] = Field(default_factory=list)
