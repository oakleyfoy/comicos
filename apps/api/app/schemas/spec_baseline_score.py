from __future__ import annotations

from pydantic import BaseModel, Field


class SpecBaselineScoreRead(BaseModel):
    id: int
    owner_id: int
    spec_input_id: int
    release_id: int | None
    title: str
    publisher: str
    series_name: str
    issue_number: str
    baseline_score: float
    confidence_score: float
    risk_score: float
    rationale: str
    created_at: str


class SpecBaselineScoreListRead(BaseModel):
    items: list[SpecBaselineScoreRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class SpecBaselineScoreLatestRead(BaseModel):
    scores_computed: int
    scores_skipped: int
    scores_updated: int
    items: list[SpecBaselineScoreRead] = Field(default_factory=list)


class SpecBaselineScoreSummaryRead(BaseModel):
    total_scores: int = Field(default=0, ge=0)
    average_baseline_score: float = Field(default=0.0, ge=0.0)
    average_confidence_score: float = Field(default=0.0, ge=0.0)
    average_risk_score: float = Field(default=0.0, ge=0.0)
    high_baseline_count: int = Field(default=0, ge=0)
