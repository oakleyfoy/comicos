from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CatalogImportJob(SQLModel, table=True):
    __tablename__ = "catalog_import_job"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    job_type: str = Field(max_length=64, nullable=False, index=True)
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    cursor: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    total_seen: int = Field(default=0, nullable=False)
    total_created: int = Field(default=0, nullable=False)
    total_updated: int = Field(default=0, nullable=False)
    total_skipped: int = Field(default=0, nullable=False)
    total_failed: int = Field(default=0, nullable=False)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    config: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogImportError(SQLModel, table=True):
    __tablename__ = "catalog_import_error"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="catalog_import_job.id", nullable=False, index=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    external_id: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    record_type: str | None = Field(default=None, max_length=64, nullable=True)
    error_type: str | None = Field(default=None, max_length=64, nullable=True)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    raw_payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogUpcConflict(SQLModel, table=True):
    __tablename__ = "catalog_upc_conflict"

    id: int | None = Field(default=None, primary_key=True)
    normalized_upc: str = Field(max_length=64, nullable=False, index=True)
    existing_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    existing_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    incoming_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    incoming_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    existing_source: str | None = Field(default=None, max_length=64, nullable=True)
    incoming_source: str | None = Field(default=None, max_length=64, nullable=True)
    status: str = Field(default="open", max_length=32, nullable=False, index=True)
    details: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogDuplicateCandidate(SQLModel, table=True):
    __tablename__ = "catalog_duplicate_candidate"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=32, nullable=False, index=True)
    primary_entity_id: int = Field(nullable=False, index=True)
    duplicate_entity_id: int = Field(nullable=False, index=True)
    confidence: Decimal = Field(sa_column=Column(Numeric(5, 4), nullable=False))
    reasons: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogMergeEvent(SQLModel, table=True):
    __tablename__ = "catalog_merge_event"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=32, nullable=False, index=True)
    survivor_id: int = Field(nullable=False, index=True)
    merged_id: int = Field(nullable=False, index=True)
    reasons: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecognitionCertificationRun(SQLModel, table=True):
    __tablename__ = "recognition_certification_run"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False)
    dataset_name: str = Field(max_length=255, nullable=False, index=True)
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    total_items: int = Field(default=0, nullable=False)
    upc_matches: int = Field(default=0, nullable=False)
    cover_matches: int = Field(default=0, nullable=False)
    ocr_matches: int = Field(default=0, nullable=False)
    manual_required: int = Field(default=0, nullable=False)
    failures: int = Field(default=0, nullable=False)
    avg_recognition_ms: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    recognition_rate: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 4), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecognitionCertificationItem(SQLModel, table=True):
    __tablename__ = "recognition_certification_item"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="recognition_certification_run.id", nullable=False, index=True)
    expected_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    expected_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    test_upc: str | None = Field(default=None, max_length=64, nullable=True)
    test_image_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    expected_label: str | None = Field(default=None, max_length=255, nullable=True)
    actual_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    actual_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    method: str | None = Field(default=None, max_length=32, nullable=True)
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 4), nullable=True))
    recognition_ms: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecognitionGap(SQLModel, table=True):
    __tablename__ = "recognition_gap"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    scan_session_id: int | None = Field(default=None, foreign_key="inventory_scan_session.id", nullable=True, index=True)
    scan_item_id: int | None = Field(default=None, foreign_key="inventory_scan_item.id", nullable=True, index=True)
    certification_run_id: int | None = Field(default=None, foreign_key="recognition_certification_run.id", nullable=True, index=True)
    certification_item_id: int | None = Field(default=None, foreign_key="recognition_certification_item.id", nullable=True, index=True)
    gap_type: str = Field(max_length=64, nullable=False, index=True)
    submitted_upc: str | None = Field(default=None, max_length=64, nullable=True)
    submitted_image_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    submitted_ocr_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    expected_label: str | None = Field(default=None, max_length=255, nullable=True)
    predicted_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    predicted_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 4), nullable=True))
    status: str = Field(default="open", max_length=32, nullable=False, index=True)
    resolution_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
