"""Async intake queue: hands-free scanning + background identification.

The scanner is capture-only. Each scan immediately creates an ``IntakeSessionItem`` with
status ``queued`` and returns to the camera. Background workers identify items later;
identification and review are separate workflows from capture.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- Intake session lifecycle (phone scanner controls) ---
INTAKE_SESSION_ACTIVE = "active"
INTAKE_SESSION_PAUSED = "paused"
INTAKE_SESSION_STOPPED = "stopped"
INTAKE_SESSION_EXPIRED = "expired"

# --- Per-item processing lifecycle ---
ITEM_QUEUED = "queued"
ITEM_PROCESSING = "processing"
ITEM_AUTO_MATCHED = "auto_matched"          # high-confidence exact match (learned map / catalog UPC)
ITEM_READY_FOR_REVIEW = "ready_for_review"  # candidate found (e.g. ComicVine), needs confirm
ITEM_NEEDS_REVIEW = "needs_review"          # ambiguous / no safe match
ITEM_FAILED = "failed"                      # could not read barcode / processing error
ITEM_ADDED_TO_INVENTORY = "added_to_inventory"
ITEM_REJECTED = "rejected"

# Match sources for learned mappings + diagnostics.
MATCH_SOURCE_LEARNED = "learned_barcode"
MATCH_SOURCE_CATALOG_UPC = "catalog_upc"
MATCH_SOURCE_COMICVINE = "comicvine"
MATCH_SOURCE_MANUAL = "manual"


class IntakeSession(SQLModel, table=True):
    __tablename__ = "intake_session"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    session_token: str = Field(max_length=64, unique=True, index=True, nullable=False)
    name: str | None = Field(default=None, max_length=256, nullable=True)
    status: str = Field(max_length=32, default=INTAKE_SESSION_ACTIVE, nullable=False)
    source_device: str | None = Field(default=None, max_length=128, nullable=True)
    scanned_count: int = Field(default=0, nullable=False)
    acquisition_id: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    expires_at: datetime = Field(nullable=False)
    last_seen_at: datetime | None = Field(default=None, nullable=True)


class IntakeSessionItem(SQLModel, table=True):
    __tablename__ = "intake_session_item"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="intake_session.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    # Captured image.
    storage_path: str = Field(max_length=1024, nullable=False)
    mime_type: str = Field(max_length=128, default="image/jpeg", nullable=False)
    file_size: int = Field(default=0, nullable=False)

    # Barcode (raw detected on the phone if fast, otherwise filled by the worker).
    raw_barcode: str | None = Field(default=None, max_length=64, nullable=True)
    normalized_barcode: str | None = Field(default=None, max_length=64, index=True, nullable=True)
    base_upc: str | None = Field(default=None, max_length=16, nullable=True)
    extension: str | None = Field(default=None, max_length=8, nullable=True)

    status: str = Field(max_length=32, default=ITEM_QUEUED, index=True, nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    match_source: str | None = Field(default=None, max_length=32, nullable=True)

    # Selected/identified catalog record.
    selected_catalog_issue_id: int | None = Field(default=None, index=True, nullable=True)
    selected_variant_id: int | None = Field(default=None, nullable=True)
    matched_publisher: str | None = Field(default=None, max_length=256, nullable=True)
    matched_series: str | None = Field(default=None, max_length=512, nullable=True)
    matched_issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    matched_year: str | None = Field(default=None, max_length=16, nullable=True)
    cover_url: str | None = Field(default=None, max_length=2048, nullable=True)

    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    acquisition_id: int | None = Field(default=None, nullable=True)
    inventory_copy_id: int | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    processed_at: datetime | None = Field(default=None, nullable=True)


class IntakeItemCandidate(SQLModel, table=True):
    __tablename__ = "intake_item_candidate"

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="intake_session_item.id", index=True, nullable=False)
    catalog_issue_id: int | None = Field(default=None, index=True, nullable=True)
    variant_id: int | None = Field(default=None, nullable=True)
    publisher: str | None = Field(default=None, max_length=256, nullable=True)
    series: str | None = Field(default=None, max_length=512, nullable=True)
    issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    cover_url: str | None = Field(default=None, max_length=2048, nullable=True)
    score: float = Field(default=0.0, nullable=False)
    source: str | None = Field(default=None, max_length=32, nullable=True)
    rank: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class ComicIssueBarcode(SQLModel, table=True):
    """Learned barcode -> catalog issue mapping so future scans match instantly."""

    __tablename__ = "comic_issue_barcodes"

    id: int | None = Field(default=None, primary_key=True)
    normalized_barcode: str = Field(max_length=64, unique=True, index=True, nullable=False)
    catalog_issue_id: int = Field(index=True, nullable=False)
    variant_id: int | None = Field(default=None, nullable=True)
    source: str = Field(max_length=32, default=MATCH_SOURCE_MANUAL, nullable=False)
    confirmed_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True)
    times_seen: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
