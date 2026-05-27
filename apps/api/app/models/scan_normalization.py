from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanNormalizationRun(SQLModel, table=True):
    __tablename__ = "scan_normalization_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "normalization_checksum", name="uq_scan_norm_run_owner_checksum"),
        SAIndex("ix_scan_norm_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_norm_run_owner_status", "owner_user_id", "normalization_status", "id"),
        SAIndex("ix_scan_norm_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    source_sha256_checksum: str = Field(max_length=64, nullable=False, index=True)
    normalization_checksum: str = Field(max_length=64, nullable=False, index=True)
    normalization_status: str = Field(max_length=24, nullable=False, index=True)
    orientation_code: str = Field(max_length=24, nullable=False, index=True)
    rotation_degrees: int = Field(default=0, nullable=False)
    crop_left: int = Field(default=0, nullable=False)
    crop_top: int = Field(default=0, nullable=False)
    crop_right: int = Field(default=0, nullable=False)
    crop_bottom: int = Field(default=0, nullable=False)
    perspective_strength: int = Field(default=0, nullable=False)
    issue_count: int = Field(default=0, nullable=False)
    artifact_count: int = Field(default=0, nullable=False)
    replayed_from_run_id: int | None = Field(default=None, foreign_key="scan_normalization_run.id", nullable=True, index=True)
    final_artifact_id: int | None = Field(default=None, nullable=True, index=True)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanNormalizationArtifact(SQLModel, table=True):
    __tablename__ = "scan_normalization_artifact"
    __table_args__ = (
        UniqueConstraint(
            "scan_normalization_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_norm_art_run_type_checksum",
        ),
        SAIndex("ix_scan_norm_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_norm_art_scan_image", "scan_image_id", "artifact_order", "id"),
        SAIndex("ix_scan_norm_art_status", "normalization_status", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    parent_artifact_id: int | None = Field(default=None, foreign_key="scan_normalization_artifact.id", nullable=True, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    artifact_order: int = Field(default=0, nullable=False)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    width: int = Field(nullable=False)
    height: int = Field(nullable=False)
    dpi_x: int | None = Field(default=None, nullable=True)
    dpi_y: int | None = Field(default=None, nullable=True)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    parent_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    normalization_status: str = Field(max_length=24, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanNormalizationIssue(SQLModel, table=True):
    __tablename__ = "scan_normalization_issue"
    __table_args__ = (
        SAIndex("ix_scan_norm_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_norm_issue_scan_image", "scan_image_id", "issue_type", "id"),
        SAIndex("ix_scan_norm_issue_status", "normalization_status", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    issue_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    normalization_status: str = Field(max_length=24, nullable=False, index=True)
    metric_value: str | None = Field(default=None, max_length=64, nullable=True)
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanNormalizationHistory(SQLModel, table=True):
    __tablename__ = "scan_normalization_history"
    __table_args__ = (
        SAIndex("ix_scan_norm_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_norm_hist_run_order", "scan_normalization_run_id", "history_order", "id"),
        SAIndex("ix_scan_norm_hist_scan_image", "scan_image_id", "stage_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    history_order: int = Field(default=0, nullable=False)
    stage_name: str = Field(max_length=40, nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    from_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    to_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
