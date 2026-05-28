from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanSpineTickRun(SQLModel, table=True):
    __tablename__ = "scan_spine_tick_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "spine_tick_checksum", name="uq_scan_spine_tick_run_owner_checksum"),
        SAIndex("ix_scan_spine_tick_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_run_defect", "defect_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    defect_run_id: int = Field(foreign_key="scan_defect_run.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    spine_tick_checksum: str = Field(max_length=64, nullable=False, index=True)
    detection_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanSpineTickEvidence(SQLModel, table=True):
    __tablename__ = "scan_spine_tick_evidence"
    __table_args__ = (
        SAIndex("ix_scan_spine_tick_evidence_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_evidence_run_rank", "spine_tick_run_id", "tick_rank", "id"),
        SAIndex("ix_scan_spine_tick_evidence_run_conf", "spine_tick_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spine_tick_run_id: int = Field(foreign_key="scan_spine_tick_run.id", nullable=False, index=True)
    defect_evidence_id: int | None = Field(
        default=None,
        foreign_key="scan_defect_evidence.id",
        nullable=True,
        index=True,
    )
    tick_rank: int = Field(nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    severity_hint: str = Field(max_length=16, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    width_px: int = Field(nullable=False)
    height_px: int = Field(nullable=False)
    angle_degrees: float = Field(default=0.0, nullable=False)
    edge_distance_px: int = Field(default=0, nullable=False)
    spine_overlap_ratio: float = Field(default=0.0, nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanSpineTickArtifact(SQLModel, table=True):
    __tablename__ = "scan_spine_tick_artifact"
    __table_args__ = (
        UniqueConstraint(
            "spine_tick_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_spine_tick_art_run_type_checksum",
        ),
        SAIndex("ix_scan_spine_tick_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_art_run_type", "spine_tick_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spine_tick_run_id: int = Field(foreign_key="scan_spine_tick_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanSpineTickIssue(SQLModel, table=True):
    __tablename__ = "scan_spine_tick_issue"
    __table_args__ = (
        SAIndex("ix_scan_spine_tick_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_issue_run_type", "spine_tick_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spine_tick_run_id: int = Field(foreign_key="scan_spine_tick_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanSpineTickHistory(SQLModel, table=True):
    __tablename__ = "scan_spine_tick_history"
    __table_args__ = (
        SAIndex("ix_scan_spine_tick_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_spine_tick_hist_run_type", "spine_tick_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spine_tick_run_id: int = Field(foreign_key="scan_spine_tick_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
