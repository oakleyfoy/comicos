from __future__ import annotations

from pydantic import BaseModel, Field


class SpecInputRead(BaseModel):
    id: int
    owner_id: int
    release_id: int | None
    industry_candidate_id: int | None
    future_release_match_id: int | None
    title: str
    publisher: str
    series_name: str
    issue_number: str
    foc_date: str | None
    release_date: str | None
    source_systems: list[str] = Field(default_factory=list)
    signal_summary: str
    created_at: str


class SpecInputListRead(BaseModel):
    items: list[SpecInputRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class SpecInputLatestRead(BaseModel):
    items: list[SpecInputRead] = Field(default_factory=list)
    inputs_created: int = Field(default=0, ge=0)
    inputs_skipped: int = Field(default=0, ge=0)
    inputs_updated: int = Field(default=0, ge=0)


class SpecInputSummaryRead(BaseModel):
    total_inputs: int = Field(default=0, ge=0)
    unique_releases: int = Field(default=0, ge=0)
    with_industry_candidate: int = Field(default=0, ge=0)
    with_future_match: int = Field(default=0, ge=0)
    source_system_counts: dict[str, int] = Field(default_factory=dict)
