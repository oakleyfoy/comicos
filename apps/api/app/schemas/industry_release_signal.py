from __future__ import annotations

from pydantic import BaseModel, Field


class IndustryReleaseSignalRead(BaseModel):
    id: int
    owner_id: int
    candidate_id: int
    scan_run_id: int
    release_id: int
    publisher_code: str
    publisher_name: str
    series_name: str
    issue_number: str
    signal_type: str
    confidence_score: float
    rationale: str
    created_at: str
    updated_at: str


class IndustryReleaseSignalListRead(BaseModel):
    items: list[IndustryReleaseSignalRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class IndustryReleaseSignalLatestRead(BaseModel):
    scan_run_id: int | None = None
    signals_classified: int = Field(default=0, ge=0)
    items: list[IndustryReleaseSignalRead] = Field(default_factory=list)
