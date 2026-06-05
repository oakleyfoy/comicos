from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ExternalCatalogIssueRead(BaseModel):
    id: int
    source_name: str
    source_issue_id: str | None
    source_url: str | None
    title: str
    publisher: str
    series_name: str
    issue_number: str | None
    release_date: date | None
    foc_date: date | None
    pull_count: int | None
    want_count: int | None
    variant_count: int | None
    cover_image_url: str | None
    thumbnail_url: str | None
    high_resolution_image_url: str | None
    product_url: str | None
    description: str | None
    story_summary: str | None
    imprint: str | None
    universe: str | None
    is_first_issue: bool
    is_milestone_issue: bool
    milestone_issue_number: int | None
    importance_signals_json: dict | None
    decision_signals_json: dict | None
    sync_status: str
    last_seen_at: datetime


class ExternalCatalogIssueListRead(BaseModel):
    items: list[ExternalCatalogIssueRead]
    total_items: int
    limit: int
    offset: int


class ExternalCatalogSyncRunRead(BaseModel):
    id: int
    source_name: str
    sync_type: str
    status: str
    pages_scanned: int
    issues_created: int
    issues_updated: int
    errors_count: int
    started_at: datetime
    completed_at: datetime | None


class ExternalCatalogCrosswalkRebuildRead(BaseModel):
    total: int
    matched: int
    missing_from_lunar: int
    possible_duplicate: int
    needs_review: int
