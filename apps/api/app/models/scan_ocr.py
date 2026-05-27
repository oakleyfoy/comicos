from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanOcrRun(SQLModel, table=True):
    __tablename__ = "scan_ocr_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "ocr_checksum", name="uq_scan_ocr_run_owner_checksum"),
        SAIndex("ix_scan_ocr_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_run_owner_status", "owner_user_id", "ocr_status", "id"),
        SAIndex("ix_scan_ocr_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_run_boundary", "boundary_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    source_artifact_id: int = Field(foreign_key="scan_normalization_artifact.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    ocr_checksum: str = Field(max_length=64, nullable=False, index=True)
    ocr_status: str = Field(max_length=24, nullable=False, index=True)
    ocr_engine: str = Field(max_length=40, nullable=False, index=True)
    ocr_engine_version: str | None = Field(default=None, max_length=255, nullable=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanOcrTextRegion(SQLModel, table=True):
    __tablename__ = "scan_ocr_text_region"
    __table_args__ = (
        SAIndex("ix_scan_ocr_region_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_region_run_type", "ocr_run_id", "region_type", "id"),
        SAIndex("ix_scan_ocr_region_confidence", "ocr_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    region_type: str = Field(max_length=40, nullable=False, index=True)
    extracted_text: str = Field(default="", max_length=20000, nullable=False)
    normalized_text: str | None = Field(default=None, max_length=20000, nullable=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    width_px: int = Field(nullable=False)
    height_px: int = Field(nullable=False)
    rotation_angle: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanOcrCandidate(SQLModel, table=True):
    __tablename__ = "scan_ocr_candidate"
    __table_args__ = (
        SAIndex("ix_scan_ocr_candidate_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_candidate_run_type", "ocr_run_id", "candidate_type", "id"),
        SAIndex("ix_scan_ocr_candidate_confidence", "ocr_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    candidate_type: str = Field(max_length=32, nullable=False, index=True)
    candidate_value: str = Field(max_length=2000, nullable=False)
    normalized_candidate_value: str | None = Field(default=None, max_length=2000, nullable=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    source_region_id: int | None = Field(default=None, foreign_key="scan_ocr_text_region.id", nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanOcrArtifact(SQLModel, table=True):
    __tablename__ = "scan_ocr_artifact"
    __table_args__ = (
        UniqueConstraint("ocr_run_id", "artifact_type", "artifact_checksum", name="uq_scan_ocr_art_run_type_checksum"),
        SAIndex("ix_scan_ocr_artifact_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_artifact_run_type", "ocr_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanOcrIssue(SQLModel, table=True):
    __tablename__ = "scan_ocr_issue"
    __table_args__ = (
        SAIndex("ix_scan_ocr_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_issue_run_type", "ocr_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanOcrHistory(SQLModel, table=True):
    __tablename__ = "scan_ocr_history"
    __table_args__ = (
        SAIndex("ix_scan_ocr_history_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_ocr_history_run_type", "ocr_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
