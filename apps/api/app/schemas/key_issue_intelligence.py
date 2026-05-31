from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class KeyIssueScoreBreakdownRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    importance_score: float
    collector_importance: float
    historical_importance: float
    franchise_importance: float
    overall_key_issue_score: float


class KeyIssueProfileRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    release_issue_id: int
    issue_number: str
    title: str
    series_name: str
    publisher: str
    key_issue_type: str
    importance_score: float
    confidence_score: float
    classification: str
    scores: KeyIssueScoreBreakdownRead


class KeyIssueDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_key_issues: list[KeyIssueProfileRead] = Field(default_factory=list)
    first_appearances: list[KeyIssueProfileRead] = Field(default_factory=list)
    origins: list[KeyIssueProfileRead] = Field(default_factory=list)
    milestones: list[KeyIssueProfileRead] = Field(default_factory=list)
    anniversaries: list[KeyIssueProfileRead] = Field(default_factory=list)
    universe_launches: list[KeyIssueProfileRead] = Field(default_factory=list)
    highest_importance: list[KeyIssueProfileRead] = Field(default_factory=list)
    total_profiles: int


class KeyIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[KeyIssueProfileRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class KeyIssueRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detections_created: int
    catalog_matches: int
    pattern_matches: int
    scores_updated: int
    refreshed_at: date
