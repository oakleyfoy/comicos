from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanHistoricalComparisonRun(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_runs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "historical_comparison_checksum", name="uq_scan_hist_comp_run_owner_checksum"),
        SAIndex("ix_scan_hist_comp_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_run_owner_status", "owner_user_id", "comparison_status", "id"),
        SAIndex("ix_scan_hist_comp_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    reconciliation_run_id: int | None = Field(default=None, foreign_key="scan_reconciliation_run.id", nullable=True, index=True)
    visual_evidence_run_id: int | None = Field(default=None, foreign_key="scan_visual_evidence_run.id", nullable=True, index=True)
    review_session_id: int | None = Field(default=None, foreign_key="scan_review_session.id", nullable=True, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    historical_comparison_checksum: str = Field(max_length=64, nullable=False, index=True)
    comparison_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanHistoricalComparisonPair(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_pairs"
    __table_args__ = (
        SAIndex("ix_scan_hist_comp_pair_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_pair_run_current_prior", "comparison_run_id", "current_scan_image_id", "prior_scan_image_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comparison_run_id: int = Field(foreign_key="scan_historical_comparison_runs.id", nullable=False, index=True)
    current_scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    prior_scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    current_identity_key: str = Field(max_length=1024, nullable=False, index=True)
    prior_identity_key: str = Field(max_length=1024, nullable=False, index=True)
    match_basis: str = Field(max_length=40, nullable=False, index=True)
    match_confidence: float = Field(default=0.0, nullable=False, index=True)
    current_checksum: str = Field(max_length=64, nullable=False, index=True)
    prior_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanHistoricalComparisonDelta(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_deltas"
    __table_args__ = (
        SAIndex("ix_scan_hist_comp_delta_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_delta_run_pair_rank", "comparison_run_id", "pair_id", "delta_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comparison_run_id: int = Field(foreign_key="scan_historical_comparison_runs.id", nullable=False, index=True)
    pair_id: int = Field(foreign_key="scan_historical_comparison_pairs.id", nullable=False, index=True)
    delta_rank: int = Field(nullable=False, index=True)
    delta_type: str = Field(max_length=32, nullable=False, index=True)
    delta_category: str = Field(max_length=24, nullable=False, index=True)
    delta_direction: str = Field(max_length=16, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    severity_hint: str = Field(max_length=16, nullable=False, index=True)
    region_type: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    x_min: int = Field(nullable=False)
    y_min: int = Field(nullable=False)
    x_max: int = Field(nullable=False)
    y_max: int = Field(nullable=False)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanHistoricalComparisonArtifact(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_artifacts"
    __table_args__ = (
        UniqueConstraint("comparison_run_id", "artifact_type", "artifact_checksum", name="uq_scan_hist_comp_art_run_type_checksum"),
        SAIndex("ix_scan_hist_comp_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_art_run_type", "comparison_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comparison_run_id: int = Field(foreign_key="scan_historical_comparison_runs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanHistoricalComparisonIssue(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_issues"
    __table_args__ = (
        SAIndex("ix_scan_hist_comp_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_issue_run_type", "comparison_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comparison_run_id: int = Field(foreign_key="scan_historical_comparison_runs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanHistoricalComparisonHistory(SQLModel, table=True):
    __tablename__ = "scan_historical_comparison_history"
    __table_args__ = (
        SAIndex("ix_scan_hist_comp_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_hist_comp_hist_run_type", "comparison_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comparison_run_id: int = Field(foreign_key="scan_historical_comparison_runs.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
