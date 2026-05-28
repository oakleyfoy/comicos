from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanDefectAggregationRun(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregation_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "aggregation_checksum", name="uq_scan_defect_aggregation_run_owner_checksum"),
        SAIndex("ix_scan_defect_aggregation_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregation_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    aggregation_checksum: str = Field(max_length=64, nullable=False, index=True)
    aggregation_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanDefectAggregateCluster(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregate_cluster"
    __table_args__ = (
        SAIndex("ix_scan_defect_aggregate_cluster_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregate_cluster_run_rank", "aggregation_run_id", "cluster_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    cluster_rank: int = Field(nullable=False, index=True)
    cluster_type: str = Field(max_length=32, nullable=False, index=True)
    cluster_region: str = Field(max_length=32, nullable=False, index=True)
    cluster_confidence: float = Field(default=0.0, nullable=False, index=True)
    aggregate_severity_hint: str = Field(max_length=16, nullable=False, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    cluster_area_ratio: float = Field(default=0.0, nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectAggregateEvidence(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregate_evidence"
    __table_args__ = (
        SAIndex("ix_scan_defect_aggregate_evidence_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregate_evidence_run_cluster", "aggregation_run_id", "cluster_id", "id"),
        SAIndex("ix_scan_defect_aggregate_evidence_source", "aggregation_run_id", "source_detector", "source_evidence_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    cluster_id: int = Field(foreign_key="scan_defect_aggregate_cluster.id", nullable=False, index=True)
    source_detector: str = Field(max_length=32, nullable=False, index=True)
    source_evidence_id: int = Field(nullable=False, index=True)
    evidence_type: str = Field(max_length=64, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    contribution_weight: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectAggregationArtifact(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregation_artifact"
    __table_args__ = (
        UniqueConstraint("aggregation_run_id", "artifact_type", "artifact_checksum", name="uq_scan_defect_aggregation_art_run_type_checksum"),
        SAIndex("ix_scan_defect_aggregation_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregation_art_run_type", "aggregation_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectAggregationIssue(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregation_issue"
    __table_args__ = (
        SAIndex("ix_scan_defect_aggregation_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregation_issue_run_type", "aggregation_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanDefectAggregationHistory(SQLModel, table=True):
    __tablename__ = "scan_defect_aggregation_history"
    __table_args__ = (
        SAIndex("ix_scan_defect_aggregation_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_defect_aggregation_hist_run_type", "aggregation_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    aggregation_run_id: int = Field(foreign_key="scan_defect_aggregation_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
