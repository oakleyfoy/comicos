from __future__ import annotations

from pydantic import BaseModel, Field


class IndustryOpportunityRead(BaseModel):
    id: int
    owner_id: int
    candidate_id: int
    scan_run_id: int
    release_id: int
    publisher_code: str
    publisher_name: str
    series_name: str
    issue_number: str
    opportunity_score: float
    confidence_score: float
    risk_level: str
    rationale: str
    created_at: str
    updated_at: str


class IndustryOpportunityListRead(BaseModel):
    items: list[IndustryOpportunityRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class IndustryOpportunityLatestRead(BaseModel):
    scan_run_id: int | None = None
    scores_computed: int = Field(default=0, ge=0)
    items: list[IndustryOpportunityRead] = Field(default_factory=list)


class IndustryOpportunitySummaryRead(BaseModel):
    scan_run_id: int | None = None
    total_opportunities: int = Field(default=0, ge=0)
    average_opportunity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    high_opportunity_count: int = Field(default=0, ge=0)
    low_risk_count: int = Field(default=0, ge=0)
    medium_risk_count: int = Field(default=0, ge=0)
    high_risk_count: int = Field(default=0, ge=0)
