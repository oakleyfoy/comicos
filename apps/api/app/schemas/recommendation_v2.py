from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RecommendationComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_name: str
    component_score: float
    component_weight: float
    explanation: str


class RecommendationDecisionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_summary: str
    primary_reason: str
    risk_note: str
    suggested_action: str
    suggested_quantity: int


class RecommendationV2Read(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    release_issue_id: int
    release_variant_id: int | None
    series_name: str
    issue_number: str
    title: str
    publisher: str
    total_score: float
    recommendation_tier: str
    recommendation_type: str
    confidence_score: float


class RecommendationV2DetailRead(RecommendationV2Read):
    model_config = ConfigDict(extra="forbid")

    components: list[RecommendationComponentRead]
    decision: RecommendationDecisionRead | None


class RecommendationV2ListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecommendationV2Read]
    total_items: int
    limit: int
    offset: int


class RecommendationV2RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_uuid: str
    status: str
    issues_scored: int
    variants_scored: int
    recommendations_created: int


class RecommendationV2DashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_buy: list[RecommendationV2Read]
    strong_buy: list[RecommendationV2Read]
    buy: list[RecommendationV2Read]
    watch: list[RecommendationV2Read]
    pass_tier: list[RecommendationV2Read]
    investment_number_ones: list[RecommendationV2Read]
    start_run: list[RecommendationV2Read]
    key_issues: list[RecommendationV2Read]
    ratio_variants: list[RecommendationV2Read]
    user_preference_matches: list[RecommendationV2Read]


class RecommendationComparisonEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_issue_id: int
    series_name: str
    issue_number: str
    title: str
    v1_score: float
    v2_score: float
    v1_rank: int | None
    v2_rank: int | None
    rank_change: int | None
    movement_reason: str


class RecommendationV2ComparisonRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[RecommendationComparisonEntryRead]
    books_moved_up: int
    books_moved_down: int
    v1_sample_size: int
    v2_sample_size: int
