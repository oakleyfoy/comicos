from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanGradingAssistanceRun(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "grading_assistance_checksum", name="uq_scan_grading_assist_run_owner_checksum"),
        SAIndex("ix_scan_grading_assist_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_run_aggregation", "aggregation_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    reconciliation_run_id: int | None = Field(default=None, foreign_key="scan_reconciliation_run.id", nullable=True, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    grading_assistance_checksum: str = Field(max_length=64, nullable=False, index=True)
    assistance_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    rubric_version: str = Field(max_length=64, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanGradingAssistanceCategory(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_category"
    __table_args__ = (
        SAIndex("ix_scan_grading_assist_cat_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_cat_run_type", "grading_assistance_run_id", "category_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_assistance_run_id: int = Field(foreign_key="scan_grading_assistance_run.id", nullable=False, index=True)
    category_type: str = Field(max_length=32, nullable=False, index=True)
    category_status: str = Field(max_length=24, nullable=False, index=True)
    suggested_range_low: float = Field(default=0.0, nullable=False)
    suggested_range_high: float = Field(default=0.0, nullable=False)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    evidence_count: int = Field(default=0, nullable=False)
    summary_text: str = Field(max_length=1024, nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanGradingAssistanceFinding(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_finding"
    __table_args__ = (
        SAIndex("ix_scan_grading_assist_find_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_find_run_cat", "grading_assistance_run_id", "category_id", "id"),
        SAIndex("ix_scan_grading_assist_find_run_pressure", "grading_assistance_run_id", "grade_pressure_hint", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_assistance_run_id: int = Field(foreign_key="scan_grading_assistance_run.id", nullable=False, index=True)
    category_id: int = Field(foreign_key="scan_grading_assistance_category.id", nullable=False, index=True)
    source_cluster_id: int | None = Field(default=None, foreign_key="scan_defect_aggregate_cluster.id", nullable=True, index=True)
    source_detector: str = Field(max_length=40, nullable=False, index=True)
    finding_type: str = Field(max_length=48, nullable=False, index=True)
    finding_severity_hint: str = Field(max_length=16, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    grade_pressure_hint: str = Field(max_length=16, nullable=False, index=True)
    finding_text: str = Field(max_length=1024, nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanGradingAssistanceArtifact(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_artifact"
    __table_args__ = (
        UniqueConstraint("grading_assistance_run_id", "artifact_type", "artifact_checksum", name="uq_scan_grading_assist_art_run_type_checksum"),
        SAIndex("ix_scan_grading_assist_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_art_run_type", "grading_assistance_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_assistance_run_id: int = Field(foreign_key="scan_grading_assistance_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanGradingAssistanceIssue(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_issue"
    __table_args__ = (
        SAIndex("ix_scan_grading_assist_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_issue_run_type", "grading_assistance_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_assistance_run_id: int = Field(foreign_key="scan_grading_assistance_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanGradingAssistanceHistory(SQLModel, table=True):
    __tablename__ = "scan_grading_assistance_history"
    __table_args__ = (
        SAIndex("ix_scan_grading_assist_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_grading_assist_hist_run_type", "grading_assistance_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_assistance_run_id: int = Field(foreign_key="scan_grading_assistance_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
