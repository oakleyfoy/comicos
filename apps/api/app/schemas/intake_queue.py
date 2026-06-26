"""Async intake queue API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IntakeSessionCreatePayload(BaseModel):
    source_device: str | None = None
    name: str | None = None
    acquisition_id: int


class IntakeSessionRead(BaseModel):
    id: int
    session_token: str
    name: str | None
    status: str
    source_device: str | None
    scanned_count: int
    acquisition_id: int | None
    acquisition_label: str | None
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None
    scanner_url: str
    review_url: str


class IntakeSessionStatusPayload(BaseModel):
    status: str  # active | paused | stopped


class IntakeEnqueueResponse(BaseModel):
    item_id: int
    status: str
    scanned_count: int


class IntakeCounts(BaseModel):
    scanned: int
    queued: int
    processing: int
    auto_matched: int
    ready_for_review: int
    needs_review: int
    added_to_inventory: int
    rejected: int
    failed: int


class IntakeItemCandidateRead(BaseModel):
    id: int
    catalog_issue_id: int | None
    variant_id: int | None
    publisher: str | None
    series: str | None
    issue_number: str | None
    cover_url: str | None
    score: float
    source: str | None
    rank: int


class IntakeItemRead(BaseModel):
    id: int
    session_id: int
    status: str
    confidence: float
    match_source: str | None
    raw_barcode: str | None
    normalized_barcode: str | None
    base_upc: str | None
    extension: str | None
    possible_corrected_barcode: str | None = None
    barcode_read: dict | None = None
    selected_catalog_issue_id: int | None
    selected_variant_id: int | None
    matched_publisher: str | None
    matched_series: str | None
    matched_issue_number: str | None
    matched_year: str | None
    cover_url: str | None
    reason: str | None
    error: str | None
    image_url: str
    acquisition_id: int | None
    inventory_copy_id: int | None
    created_at: datetime
    processed_at: datetime | None
    candidates: list[IntakeItemCandidateRead] = []


class IntakeReviewResponse(BaseModel):
    session: IntakeSessionRead
    counts: IntakeCounts
    items: list[IntakeItemRead]


class IntakeChooseIssuePayload(BaseModel):
    catalog_issue_id: int
    variant_id: int | None = None


class IntakeCatalogSearchResult(BaseModel):
    catalog_issue_id: int
    series: str | None
    issue_number: str | None
    publisher: str | None
    cover_url: str | None


class IntakeCatalogSearchResponse(BaseModel):
    results: list[IntakeCatalogSearchResult]


class IntakeAddAllResponse(BaseModel):
    added: int
    candidates: int
