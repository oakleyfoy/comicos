from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanUploadSession(SQLModel, table=True):
    __tablename__ = "scan_upload_session"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "session_checksum", name="uq_scan_upload_session_owner_checksum"),
        SAIndex("ix_scan_upload_session_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_upload_session_source", "upload_source", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    upload_source: str = Field(max_length=40, nullable=False, index=True)
    session_checksum: str = Field(max_length=64, nullable=False, index=True)
    total_files: int = Field(default=0, nullable=False)
    successful_files: int = Field(default=0, nullable=False)
    failed_files: int = Field(default=0, nullable=False)
    duplicate_files: int = Field(default=0, nullable=False)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanIngestionBatch(SQLModel, table=True):
    __tablename__ = "scan_ingestion_batch"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "ingestion_checksum", name="uq_scan_ingestion_batch_owner_checksum"),
        SAIndex("ix_scan_ingestion_batch_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ingestion_batch_owner_status", "owner_user_id", "batch_status", "id"),
        SAIndex("ix_scan_ingestion_batch_source", "source_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    upload_session_id: int = Field(foreign_key="scan_upload_session.id", nullable=False, index=True)
    source_type: str = Field(max_length=40, nullable=False, index=True)
    batch_status: str = Field(max_length=24, nullable=False, index=True)
    image_count: int = Field(default=0, nullable=False)
    failed_count: int = Field(default=0, nullable=False)
    duplicate_count: int = Field(default=0, nullable=False)
    ingestion_checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanImage(SQLModel, table=True):
    __tablename__ = "scan_image"
    __table_args__ = (
        UniqueConstraint("ingestion_batch_id", "sequence_index", name="uq_scan_image_batch_sequence"),
        SAIndex("ix_scan_image_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_image_owner_status", "owner_user_id", "processing_status", "id"),
        SAIndex("ix_scan_image_owner_checksum", "owner_user_id", "sha256_checksum", "id"),
        SAIndex("ix_scan_image_dup_ref", "duplicate_of_scan_image_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ingestion_batch_id: int = Field(foreign_key="scan_ingestion_batch.id", nullable=False, index=True)
    sequence_index: int = Field(nullable=False, index=True)

    original_filename: str = Field(max_length=512, nullable=False)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    mime_type: str = Field(max_length=128, nullable=False)

    width: int | None = Field(default=None, nullable=True)
    height: int | None = Field(default=None, nullable=True)
    dpi_x: int | None = Field(default=None, nullable=True)
    dpi_y: int | None = Field(default=None, nullable=True)
    normalized_dpi_x: int | None = Field(default=None, nullable=True)
    normalized_dpi_y: int | None = Field(default=None, nullable=True)
    file_size_bytes: int = Field(nullable=False)
    sha256_checksum: str = Field(max_length=64, nullable=False, index=True)

    scanner_make: str | None = Field(default=None, max_length=120, nullable=True)
    scanner_model: str | None = Field(default=None, max_length=120, nullable=True)
    scanner_profile: str | None = Field(default=None, max_length=200, nullable=True)
    color_mode: str | None = Field(default=None, max_length=40, nullable=True)

    processing_status: str = Field(max_length=24, nullable=False, index=True)
    is_duplicate: bool = Field(default=False, nullable=False, index=True)
    duplicate_of_scan_image_id: int | None = Field(
        default=None,
        sa_column=Column(ForeignKey("scan_image.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    failure_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanImageVariant(SQLModel, table=True):
    __tablename__ = "scan_image_variant"
    __table_args__ = (
        UniqueConstraint("parent_scan_image_id", "variant_type", "checksum", name="uq_scan_variant_parent_type_checksum"),
        SAIndex("ix_scan_variant_parent", "parent_scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_variant_type", "variant_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    parent_scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    variant_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    width: int = Field(nullable=False)
    height: int = Field(nullable=False)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanIngestionEvent(SQLModel, table=True):
    __tablename__ = "scan_ingestion_event"
    __table_args__ = (
        SAIndex("ix_scan_ingestion_event_batch", "ingestion_batch_id", "created_at", "id"),
        SAIndex("ix_scan_ingestion_event_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_ingestion_event_type", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    ingestion_batch_id: int = Field(foreign_key="scan_ingestion_batch.id", nullable=False, index=True)
    scan_image_id: int | None = Field(default=None, foreign_key="scan_image.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
