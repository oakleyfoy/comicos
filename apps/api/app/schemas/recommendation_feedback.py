"""P73-01 recommendation feedback summary schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation_outcome import P73RecommendationOutcomeRead


class P73RecommendationFeedbackSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations_created: int
    viewed: int
    purchased: int
    skipped: int
    watchlisted: int
    held: int
    graded: int
    listed: int
    sold: int
    attribution_matches: int
    attribution_samples: int
    attribution_accuracy_pct: float


class P73RecommendationFeedbackDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: P73RecommendationFeedbackSummaryRead
    recent_outcomes: list[P73RecommendationOutcomeRead] = Field(default_factory=list)
