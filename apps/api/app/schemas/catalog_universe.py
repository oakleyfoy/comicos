"""P99 catalog universe tree (local DB only, read-only)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CatalogUniverseSummary(BaseModel):
    total_publishers: int
    total_volumes: int
    total_issues: int
    cataloged_issues: int
    discovered_only_issues: int


class CatalogUniversePublisherNode(BaseModel):
    publisher: str
    volume_count: int
    issue_count: int


class CatalogUniversePublisherListResponse(BaseModel):
    summary: CatalogUniverseSummary
    items: list[CatalogUniversePublisherNode]
    total_count: int
    limit: int
    offset: int


class CatalogUniverseVolumeNode(BaseModel):
    volume_id: int
    title: str
    volume_name: str | None = None
    start_year: int | None = None
    comicvine_volume_id: int | None = None
    issue_count: int
    catalog_issue_count: int
    min_issue_number: str | None = None
    max_issue_number: str | None = None
    missing_issue_count: int | None = None
    source: str = Field(description="universe | catalog")


class CatalogUniverseVolumeListResponse(BaseModel):
    publisher: str
    items: list[CatalogUniverseVolumeNode]
    total_count: int
    limit: int
    offset: int


class CatalogUniverseIssueNode(BaseModel):
    issue_number: str
    normalized_issue_number: str
    issue_title: str | None = None
    release_date: date | None = None
    comicvine_issue_id: int | None = None
    catalog_issue_id: int | None = None
    series_id: int | None = None
    cover_image_url: str | None = None
    has_variants: bool = False
    cover_count: int = 0
    catalog_status: str


class CatalogUniverseIssueListResponse(BaseModel):
    volume_id: int
    volume_title: str | None = None
    items: list[CatalogUniverseIssueNode]
    total_count: int
    limit: int
    offset: int
    catalog_issue_count: int
    discovered_issue_count: int


class CatalogUniverseSearchHit(BaseModel):
    hit_type: str
    publisher: str | None = None
    volume_id: int | None = None
    volume_title: str | None = None
    catalog_issue_id: int | None = None
    issue_number: str | None = None
    issue_title: str | None = None


class CatalogUniverseSearchResponse(BaseModel):
    query: str
    hits: list[CatalogUniverseSearchHit]
    total_count: int
    limit: int
    offset: int
