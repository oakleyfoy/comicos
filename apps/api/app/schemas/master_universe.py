"""P98 Master Universe tree API schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MasterUniverseSummary(BaseModel):
    publisher_count: int
    volume_count: int
    issue_count: int
    variant_count: int


class MasterUniversePublisherNode(BaseModel):
    id: int
    name: str
    comicvine_publisher_id: int | None = None
    volume_count: int = 0
    issue_count: int = 0


class MasterUniversePublisherListResponse(BaseModel):
    summary: MasterUniverseSummary
    items: list[MasterUniversePublisherNode]
    total_count: int
    limit: int
    offset: int


class MasterUniverseVolumeNode(BaseModel):
    id: int
    comicvine_volume_id: int
    publisher_id: int
    name: str
    start_year: int | None = None
    count_of_issues: int | None = None
    issue_shell_count: int = 0
    volume_status: str


class MasterUniverseVolumeListResponse(BaseModel):
    publisher_id: int
    publisher_name: str
    items: list[MasterUniverseVolumeNode]
    total_count: int
    limit: int
    offset: int


class MasterUniverseIssueNode(BaseModel):
    id: int
    issue_number: str
    normalized_issue_number: str
    issue_title: str | None = None
    cover_date: date | None = None
    comicvine_issue_id: int | None = None
    status: str
    variant_count: int = 0


class MasterUniverseIssueListResponse(BaseModel):
    volume_id: int
    volume_name: str
    items: list[MasterUniverseIssueNode]
    total_count: int
    limit: int
    offset: int


class MasterUniverseVariantNode(BaseModel):
    id: int
    variant_type: str
    variant_name: str
    status: str
    catalog_issue_id: int | None = None
    comicvine_variant_id: int | None = None
    is_unknown_shell: bool = False


class MasterUniverseVariantListResponse(BaseModel):
    issue_id: int
    issue_number: str
    items: list[MasterUniverseVariantNode]
    total_count: int
    limit: int
    offset: int


class MasterUniverseSearchHit(BaseModel):
    hit_type: str = Field(description="publisher | volume | issue | variant")
    publisher_id: int | None = None
    publisher_name: str | None = None
    volume_id: int | None = None
    volume_name: str | None = None
    issue_id: int | None = None
    issue_number: str | None = None
    variant_id: int | None = None
    variant_label: str | None = None
    status: str | None = None


class MasterUniverseSearchResponse(BaseModel):
    query: str
    hits: list[MasterUniverseSearchHit]
    total_count: int
    limit: int
    offset: int
