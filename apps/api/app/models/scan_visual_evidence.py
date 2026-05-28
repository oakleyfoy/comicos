from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanVisualEvidenceRun(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "visual_evidence_checksum", name="uq_scan_visual_evidence_run_owner_checksum"),
        SAIndex("ix_scan_visual_evidence_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    aggregation_run_id: int | None = Field(default=None, foreign_key="scan_defect_aggregation_run.id", nullable=True, index=True)
    grading_assistance_run_id: int | None = Field(default=None, foreign_key="scan_grading_assistance_run.id", nullable=True, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    visual_evidence_checksum: str = Field(max_length=64, nullable=False, index=True)
    evidence_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanVisualEvidencePackage(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_package"
    __table_args__ = (
        SAIndex("ix_scan_visual_evidence_pkg_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_pkg_run_type", "visual_evidence_run_id", "package_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    package_type: str = Field(max_length=40, nullable=False, index=True)
    package_status: str = Field(max_length=24, nullable=False, index=True)
    package_title: str = Field(max_length=255, nullable=False)
    package_summary: str = Field(max_length=1024, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanVisualEvidenceItem(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_item"
    __table_args__ = (
        SAIndex("ix_scan_visual_evidence_item_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_item_run_pkg", "visual_evidence_run_id", "package_id", "item_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    package_id: int = Field(foreign_key="scan_visual_evidence_package.id", nullable=False, index=True)
    item_rank: int = Field(nullable=False, index=True)
    source_system: str = Field(max_length=40, nullable=False, index=True)
    source_record_id: int = Field(nullable=False, index=True)
    item_type: str = Field(max_length=48, nullable=False, index=True)
    item_title: str = Field(max_length=255, nullable=False)
    item_summary: str = Field(max_length=1024, nullable=False)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    severity_hint: str | None = Field(default=None, max_length=16, nullable=True, index=True)
    region_type: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanVisualEvidenceAnnotation(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_annotation"
    __table_args__ = (
        SAIndex("ix_scan_visual_evidence_ann_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_ann_run_item", "visual_evidence_run_id", "item_id", "display_order", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    item_id: int = Field(foreign_key="scan_visual_evidence_item.id", nullable=False, index=True)
    annotation_type: str = Field(max_length=32, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    label: str = Field(max_length=255, nullable=False)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    display_order: int = Field(nullable=False, index=True)
    style_hint: str = Field(max_length=32, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanVisualEvidenceArtifact(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_artifact"
    __table_args__ = (
        UniqueConstraint("visual_evidence_run_id", "artifact_type", "artifact_checksum", name="uq_scan_visual_evidence_art_run_type_checksum"),
        SAIndex("ix_scan_visual_evidence_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_art_run_type", "visual_evidence_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanVisualEvidenceIssue(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_issue"
    __table_args__ = (
        SAIndex("ix_scan_visual_evidence_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_issue_run_type", "visual_evidence_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanVisualEvidenceHistory(SQLModel, table=True):
    __tablename__ = "scan_visual_evidence_history"
    __table_args__ = (
        SAIndex("ix_scan_visual_evidence_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_visual_evidence_hist_run_type", "visual_evidence_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    visual_evidence_run_id: int = Field(foreign_key="scan_visual_evidence_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
