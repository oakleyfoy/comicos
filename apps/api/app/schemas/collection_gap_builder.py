from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

GapStatus = Literal["OWNED", "PLACEHOLDER_OWNED", "MISSING", "SOLD_HISTORY", "UNKNOWN"]
GapTargetPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class CollectionGapYearRow(BaseModel):
    year: int
    total_issues: int
    owned_issues: int
    missing_issues: int
    completion_percent: float


class CollectionGapYearsResponse(BaseModel):
    default_year: int = 2025
    items: list[CollectionGapYearRow]


class CollectionGapPublisherRow(BaseModel):
    publisher: str
    total_issues: int
    owned_issues: int
    missing_issues: int
    completion_percent: float
    priority_rank: int | None = None


class CollectionGapPublishersResponse(BaseModel):
    year: int
    items: list[CollectionGapPublisherRow]
    total_count: int
    limit: int
    offset: int


class CollectionGapVolumeRow(BaseModel):
    volume_id: int
    title: str
    start_year: int | None
    issue_count_in_year: int
    owned_count: int
    missing_count: int
    completion_percent: float


class CollectionGapVolumesResponse(BaseModel):
    publisher: str
    year: int
    items: list[CollectionGapVolumeRow]
    total_count: int
    limit: int
    offset: int


class CollectionGapIssueRow(BaseModel):
    issue_number: str
    issue_title: str | None = None
    release_date: date | None = None
    owned: bool
    placeholder_owned: bool
    catalog_issue_id: int | None = None
    placeholder_issue_id: int | None = None
    gap_status: GapStatus


class CollectionGapIssuesResponse(BaseModel):
    volume_id: int
    year: int
    volume_title: str | None = None
    items: list[CollectionGapIssueRow]
    total_count: int
    limit: int
    offset: int


class WantListTargetItemPayload(BaseModel):
    publisher: str
    series_title: str
    volume_id: int
    issue_number: str
    catalog_issue_id: int | None = None
    placeholder_issue_id: int | None = None


class WantListTargetCreatePayload(BaseModel):
    targets: list[WantListTargetItemPayload] = Field(min_length=1)
    priority: GapTargetPriority = "MEDIUM"


class WantListTargetCreateResponse(BaseModel):
    created_count: int
    skipped_duplicates: int
    target_ids: list[int]
