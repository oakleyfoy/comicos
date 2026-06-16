"""Catalog universe placeholder queue and linking (local DB only)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PlaceholderQueueItem(BaseModel):
    placeholder_issue_id: int
    acquisition_id: int
    acquisition_type: str | None = None
    seller_name: str | None = None
    publisher: str | None = None
    title: str
    issue_number: str | None = None
    quantity: int
    catalog_status: str
    tree_linked: bool
    variant_label: str | None = None
    raw_variant_notes: str | None = None
    created_at: datetime
    comicvine_volume_id: int | None = None


class PlaceholderQueueResponse(BaseModel):
    items: list[PlaceholderQueueItem]
    total_count: int
    limit: int
    offset: int


class PlaceholderMatchCandidate(BaseModel):
    catalog_issue_id: int
    series: str
    issue_number: str
    publisher: str | None = None
    release_date: date | None = None
    catalog_status: str = "CATALOGED"
    confidence: str
    score: float


class PlaceholderMatchCandidatesResponse(BaseModel):
    placeholder_issue_id: int
    placeholder_label: str
    candidates: list[PlaceholderMatchCandidate]


class LinkPlaceholderPayload(BaseModel):
    catalog_issue_id: int


class LinkPlaceholderResponse(BaseModel):
    placeholder_issue_id: int
    catalog_issue_id: int
    catalog_status: str
    inventory_copies_updated: int
