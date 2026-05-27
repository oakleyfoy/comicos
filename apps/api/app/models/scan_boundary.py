from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanBoundaryRun(SQLModel, table=True):
    __tablename__ = "scan_boundary_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "boundary_checksum", name="uq_scan_boundary_run_owner_checksum"),
        SAIndex("ix_scan_boundary_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_run_owner_status", "owner_user_id", "boundary_status", "id"),
        SAIndex("ix_scan_boundary_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_run_norm_run", "normalization_run_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_run_source_art", "source_artifact_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    source_artifact_id: int = Field(foreign_key="scan_normalization_artifact.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    boundary_checksum: str = Field(max_length=64, nullable=False, index=True)
    boundary_status: str = Field(max_length=24, nullable=False, index=True)
    algorithm_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanBoundaryArtifact(SQLModel, table=True):
    __tablename__ = "scan_boundary_artifact"
    __table_args__ = (
        UniqueConstraint(
            "boundary_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_boundary_art_run_type_checksum",
        ),
        SAIndex("ix_scan_boundary_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_art_scan_image", "scan_image_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    width_px: int = Field(nullable=False)
    height_px: int = Field(nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanBoundaryIssue(SQLModel, table=True):
    __tablename__ = "scan_boundary_issue"
    __table_args__ = (
        SAIndex("ix_scan_boundary_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_issue_scan_image", "scan_image_id", "issue_type", "id"),
        SAIndex("ix_scan_boundary_issue_run", "boundary_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    issue_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanBoundaryHistory(SQLModel, table=True):
    __tablename__ = "scan_boundary_history"
    __table_args__ = (
        SAIndex("ix_scan_boundary_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_hist_run", "boundary_run_id", "created_at", "id"),
        SAIndex("ix_scan_boundary_hist_scan_image", "scan_image_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
