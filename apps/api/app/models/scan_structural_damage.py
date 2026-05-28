from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanStructuralDamageRun(SQLModel, table=True):
    __tablename__ = "scan_structural_damage_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "structural_damage_checksum", name="uq_scan_structural_damage_run_owner_checksum"),
        SAIndex("ix_scan_structural_damage_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_run_defect", "defect_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    structural_damage_checksum: str = Field(max_length=64, nullable=False, index=True)
    detection_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanStructuralDamageEvidence(SQLModel, table=True):
    __tablename__ = "scan_structural_damage_evidence"
    __table_args__ = (
        SAIndex("ix_scan_structural_damage_evidence_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_evidence_run_rank", "structural_damage_run_id", "evidence_rank", "id"),
        SAIndex("ix_scan_structural_damage_evidence_run_conf", "structural_damage_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    structural_damage_run_id: int = Field(foreign_key="scan_structural_damage_run.id", nullable=False, index=True)
    defect_evidence_id: int | None = Field(default=None, foreign_key="scan_defect_evidence.id", nullable=True, index=True)
    evidence_rank: int = Field(nullable=False, index=True)
    evidence_type: str = Field(max_length=40, nullable=False, index=True)
    evidence_category: str = Field(max_length=32, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    severity_hint: str = Field(max_length=16, nullable=False, index=True)
    region_type: str = Field(max_length=40, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    width_px: int = Field(nullable=False)
    height_px: int = Field(nullable=False)
    structural_area_ratio: float = Field(default=0.0, nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanStructuralDamageArtifact(SQLModel, table=True):
    __tablename__ = "scan_structural_damage_artifact"
    __table_args__ = (
        UniqueConstraint(
            "structural_damage_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_structural_damage_art_run_type_checksum",
        ),
        SAIndex("ix_scan_structural_damage_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_art_run_type", "structural_damage_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    structural_damage_run_id: int = Field(foreign_key="scan_structural_damage_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanStructuralDamageIssue(SQLModel, table=True):
    __tablename__ = "scan_structural_damage_issue"
    __table_args__ = (
        SAIndex("ix_scan_structural_damage_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_issue_run_type", "structural_damage_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    structural_damage_run_id: int = Field(foreign_key="scan_structural_damage_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanStructuralDamageHistory(SQLModel, table=True):
    __tablename__ = "scan_structural_damage_history"
    __table_args__ = (
        SAIndex("ix_scan_structural_damage_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_structural_damage_hist_run_type", "structural_damage_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    structural_damage_run_id: int = Field(foreign_key="scan_structural_damage_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
