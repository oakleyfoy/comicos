"""P104 catalog cover assets and hydration run tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


COVER_ASSET_STATUS_PENDING = "pending"
COVER_ASSET_STATUS_DOWNLOADING = "downloading"
COVER_ASSET_STATUS_COMPLETE = "complete"
COVER_ASSET_STATUS_FAILED = "failed"
COVER_ASSET_STATUS_SKIPPED_NO_URL = "skipped_no_url"

HYDRATION_RUN_STATUS_RUNNING = "running"
HYDRATION_RUN_STATUS_COMPLETED = "completed"
HYDRATION_RUN_STATUS_FAILED = "failed"


class CatalogCoverAsset(SQLModel, table=True):
    __tablename__ = "catalog_cover_assets"
    __table_args__ = (
        UniqueConstraint("catalog_issue_id", "source_url", name="uq_catalog_cover_assets_issue_url"),
        SAIndex("ix_catalog_cover_assets_status_priority", "status", "priority_score", "id"),
        SAIndex("ix_catalog_cover_assets_issue", "catalog_issue_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    catalog_issue_id: int = Field(foreign_key="catalog_issue.id", nullable=False, index=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    source_url: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default=COVER_ASSET_STATUS_PENDING, max_length=32, nullable=False, index=True)
    priority_score: int = Field(default=500, nullable=False, index=True)
    priority_tier: str = Field(default="catalog", max_length=32, nullable=False)
    original_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    thumbnail_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    small_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    medium_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    large_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    original_sha256: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    perceptual_hash: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    average_hash: str | None = Field(default=None, max_length=64, nullable=True)
    difference_hash: str | None = Field(default=None, max_length=64, nullable=True)
    color_histogram: str | None = Field(default=None, max_length=64, nullable=True)
    width: int | None = Field(default=None, nullable=True)
    height: int | None = Field(default=None, nullable=True)
    file_size: int | None = Field(default=None, nullable=True)
    download_attempts: int = Field(default=0, nullable=False)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    next_retry_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    downloaded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    verified_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogCoverHydrationRun(SQLModel, table=True):
    __tablename__ = "catalog_cover_hydration_runs"

    id: int | None = Field(default=None, primary_key=True)
    mode: str = Field(max_length=32, nullable=False, index=True)
    limit: int = Field(default=0, nullable=False)
    status: str = Field(default=HYDRATION_RUN_STATUS_RUNNING, max_length=32, nullable=False, index=True)
    requested: int = Field(default=0, nullable=False)
    queued: int = Field(default=0, nullable=False)
    downloaded: int = Field(default=0, nullable=False)
    completed: int = Field(default=0, nullable=False)
    failed: int = Field(default=0, nullable=False)
    skipped_no_url: int = Field(default=0, nullable=False)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    log_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
