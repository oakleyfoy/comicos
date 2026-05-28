from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanIntelligenceFeedRun(SQLModel, table=True):
    __tablename__ = "scan_intelligence_feed_runs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "feed_checksum", name="uq_scan_feed_run_owner_checksum"),
        SAIndex("ix_scan_feed_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_feed_run_owner_status", "owner_user_id", "feed_status", "id"),
        SAIndex("ix_scan_feed_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    upload_session_id: int | None = Field(default=None, foreign_key="scan_upload_session.id", nullable=True, index=True)
    ingestion_batch_id: int | None = Field(default=None, foreign_key="scan_ingestion_batch.id", nullable=True, index=True)
    normalization_run_id: int | None = Field(default=None, foreign_key="scan_normalization_run.id", nullable=True, index=True)
    boundary_run_id: int | None = Field(default=None, foreign_key="scan_boundary_run.id", nullable=True, index=True)
    ocr_run_id: int | None = Field(default=None, foreign_key="scan_ocr_run.id", nullable=True, index=True)
    reconciliation_run_id: int | None = Field(default=None, foreign_key="scan_reconciliation_run.id", nullable=True, index=True)
    defect_run_id: int | None = Field(default=None, foreign_key="scan_defect_run.id", nullable=True, index=True)
    spine_tick_run_id: int | None = Field(default=None, foreign_key="scan_spine_tick_run.id", nullable=True, index=True)
    corner_edge_run_id: int | None = Field(default=None, foreign_key="scan_corner_edge_run.id", nullable=True, index=True)
    surface_defect_run_id: int | None = Field(default=None, foreign_key="scan_surface_defect_run.id", nullable=True, index=True)
    structural_damage_run_id: int | None = Field(default=None, foreign_key="scan_structural_damage_run.id", nullable=True, index=True)
    defect_aggregation_run_id: int | None = Field(default=None, foreign_key="scan_defect_aggregation_run.id", nullable=True, index=True)
    grading_assistance_run_id: int | None = Field(default=None, foreign_key="scan_grading_assistance_run.id", nullable=True, index=True)
    visual_evidence_run_id: int | None = Field(default=None, foreign_key="scan_visual_evidence_run.id", nullable=True, index=True)
    review_session_id: int | None = Field(default=None, foreign_key="scan_review_session.id", nullable=True, index=True)
    historical_comparison_run_id: int | None = Field(default=None, foreign_key="scan_historical_comparison_runs.id", nullable=True, index=True)
    authentication_run_id: int | None = Field(default=None, foreign_key="scan_authentication_runs.id", nullable=True, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    feed_checksum: str = Field(max_length=64, nullable=False, index=True)
    feed_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    total_events: int = Field(default=0, nullable=False)
    total_issues: int = Field(default=0, nullable=False)
    review_required_count: int = Field(default=0, nullable=False)
    error_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanIntelligenceFeedEvent(SQLModel, table=True):
    __tablename__ = "scan_intelligence_feed_events"
    __table_args__ = (
        UniqueConstraint("feed_run_id", "event_key", name="uq_scan_feed_event_run_key"),
        SAIndex("ix_scan_feed_event_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_feed_event_run_rank", "feed_run_id", "event_rank", "id"),
        SAIndex("ix_scan_feed_event_run_timeline", "feed_run_id", "timeline_rank", "id"),
        SAIndex("ix_scan_feed_event_owner_severity", "owner_user_id", "severity", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    feed_run_id: int = Field(foreign_key="scan_intelligence_feed_runs.id", nullable=False, index=True)
    event_rank: int = Field(nullable=False, index=True)
    timeline_rank: int = Field(nullable=False, index=True)
    event_category: str = Field(max_length=40, nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    severity: str = Field(max_length=24, nullable=False, index=True)
    source_system: str = Field(max_length=48, nullable=False, index=True)
    event_occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    source_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    lineage_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    event_key: str = Field(max_length=255, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanIntelligenceFeedArtifact(SQLModel, table=True):
    __tablename__ = "scan_intelligence_feed_artifacts"
    __table_args__ = (
        UniqueConstraint("feed_run_id", "artifact_type", "artifact_checksum", name="uq_scan_feed_art_run_type_checksum"),
        SAIndex("ix_scan_feed_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_feed_art_run_type", "feed_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    feed_run_id: int = Field(foreign_key="scan_intelligence_feed_runs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanIntelligenceFeedIssue(SQLModel, table=True):
    __tablename__ = "scan_intelligence_feed_issues"
    __table_args__ = (
        UniqueConstraint("feed_run_id", "issue_checksum", name="uq_scan_feed_issue_run_checksum"),
        SAIndex("ix_scan_feed_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_feed_issue_run_type", "feed_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    feed_run_id: int = Field(foreign_key="scan_intelligence_feed_runs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=80, nullable=False, index=True)
    severity: str = Field(max_length=24, nullable=False, index=True)
    source_system: str = Field(max_length=48, nullable=False, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanIntelligenceFeedHistory(SQLModel, table=True):
    __tablename__ = "scan_intelligence_feed_history"
    __table_args__ = (
        UniqueConstraint("feed_run_id", "event_checksum", name="uq_scan_feed_history_run_checksum"),
        SAIndex("ix_scan_feed_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_feed_hist_run_type", "feed_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    feed_run_id: int = Field(foreign_key="scan_intelligence_feed_runs.id", nullable=False, index=True)
    event_type: str = Field(max_length=64, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
