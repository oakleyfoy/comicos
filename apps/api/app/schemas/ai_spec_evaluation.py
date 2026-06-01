from __future__ import annotations

from pydantic import BaseModel, Field


class AISpecEvaluationRead(BaseModel):
    id: int
    owner_id: int
    spec_input_id: int
    baseline_score_id: int
    release_id: int | None
    title: str
    publisher: str
    series_name: str
    issue_number: str
    ai_score: float
    ai_confidence: float
    risk_level: str
    ai_rationale: str
    model_name: str
    prompt_version: str
    evaluation_status: str
    created_at: str


class AISpecEvaluationListRead(BaseModel):
    items: list[AISpecEvaluationRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class AISpecEvaluationLatestRead(BaseModel):
    evaluations_computed: int = Field(default=0, ge=0)
    evaluations_skipped: int = Field(default=0, ge=0)
    evaluations_updated: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)
    items: list[AISpecEvaluationRead] = Field(default_factory=list)


class AISpecEvaluationSummaryRead(BaseModel):
    total_evaluations: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)
    average_ai_score: float = Field(default=0.0, ge=0.0)
    average_ai_confidence: float = Field(default=0.0, ge=0.0)
    low_risk_count: int = Field(default=0, ge=0)
    medium_risk_count: int = Field(default=0, ge=0)
    high_risk_count: int = Field(default=0, ge=0)
