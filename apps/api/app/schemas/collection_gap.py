from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CollectionGapType = Literal["MISSING_ISSUE", "RUN_GAP", "KEY_MISSING", "MILESTONE_MISSING"]
CollectionGapPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class CollectionGapRead(BaseModel):
    id: int
    owner_id: int
    publisher: str
    series_name: str
    issue_number: str
    gap_type: CollectionGapType
    completion_percent: float
    priority: CollectionGapPriority
    rationale: str
    created_at: str


class CollectionGapSummaryRead(BaseModel):
    total_gaps: int
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    average_completion_percent: float = 0.0


class CollectionGapListRead(BaseModel):
    items: list[CollectionGapRead]
    total_items: int
    limit: int
    offset: int


class CollectionGapGenerateResponse(BaseModel):
    created_count: int


class CollectionGapWantListSuggestionRead(BaseModel):
    publisher: str
    series_name: str
    issue_number: str
    priority: CollectionGapPriority
    gap_type: CollectionGapType
    rationale: str
