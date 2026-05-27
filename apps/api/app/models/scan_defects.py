from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanDefectRun(SQLModel, table=True):
    __tablename__ = "scan_defect_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "defect_checksum", name="uq_scan_defect_run_owner_checksum"),
        SAIndex("ix_scan_defect_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_run_owner_status", "owner_user_id", "defect_status", "id"),
        SAIndex("ix_scan_defect_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_defect_run_boundary", "boundary_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    ocr_run_id: int | None = Field(default=None, foreign_key="scan_ocr_run.id", nullable=True, index=True)
    reconciliation_run_id: int | None = Field(
        default=None,
        foreign_key="scan_reconciliation_run.id",
        nullable=True,
        index=True,
    )
    source_artifact_id: int = Field(foreign_key="scan_normalization_artifact.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    defect_checksum: str = Field(max_length=64, nullable=False, index=True)
    defect_status: str = Field(max_length=40, nullable=False, index=True)
    detection_engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanDefectRegion(SQLModel, table=True):
    __tablename__ = "scan_defect_region"
    __table_args__ = (
        UniqueConstraint("defect_run_id", "region_type", "region_checksum", name="uq_scan_defect_region_run_type_checksum"),
        SAIndex("ix_scan_defect_region_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_region_run_type", "defect_run_id", "region_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    region_type: str = Field(max_length=40, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    width_px: int = Field(nullable=False)
    height_px: int = Field(nullable=False)
    region_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectEvidence(SQLModel, table=True):
    __tablename__ = "scan_defect_evidence"
    __table_args__ = (
        SAIndex("ix_scan_defect_evidence_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_evidence_run_region", "defect_run_id", "region_id", "id"),
        SAIndex("ix_scan_defect_evidence_run_conf", "defect_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    region_id: int = Field(foreign_key="scan_defect_region.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=64, nullable=False, index=True)
    evidence_category: str = Field(max_length=40, nullable=False, index=True)
    severity_hint: str = Field(max_length=16, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectArtifact(SQLModel, table=True):
    __tablename__ = "scan_defect_artifact"
    __table_args__ = (
        UniqueConstraint("defect_run_id", "artifact_type", "artifact_checksum", name="uq_scan_defect_art_run_type_checksum"),
        SAIndex("ix_scan_defect_artifact_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_artifact_run_type", "defect_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectIssue(SQLModel, table=True):
    __tablename__ = "scan_defect_issue"
    __table_args__ = (
        SAIndex("ix_scan_defect_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_issue_run_type", "defect_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectHistory(SQLModel, table=True):
    __tablename__ = "scan_defect_history"
    __table_args__ = (
        SAIndex("ix_scan_defect_history_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_history_run_type", "defect_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
