from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanAuthenticationRun(SQLModel, table=True):
    __tablename__ = "scan_authentication_runs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "authentication_checksum", name="uq_scan_auth_run_owner_checksum"),
        SAIndex("ix_scan_auth_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_run_owner_status", "owner_user_id", "authentication_status", "id"),
        SAIndex("ix_scan_auth_run_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    reconciliation_run_id: int | None = Field(default=None, foreign_key="scan_reconciliation_run.id", nullable=True, index=True)
    visual_evidence_run_id: int | None = Field(default=None, foreign_key="scan_visual_evidence_run.id", nullable=True, index=True)
    historical_comparison_run_id: int | None = Field(default=None, foreign_key="scan_historical_comparison_runs.id", nullable=True, index=True)
    review_session_id: int | None = Field(default=None, foreign_key="scan_review_session.id", nullable=True, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    authentication_checksum: str = Field(max_length=64, nullable=False, index=True)
    authentication_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    rubric_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanAuthenticationSignal(SQLModel, table=True):
    __tablename__ = "scan_authentication_signals"
    __table_args__ = (
        SAIndex("ix_scan_auth_signal_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_signal_run_rank", "authentication_run_id", "signal_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    authentication_run_id: int = Field(foreign_key="scan_authentication_runs.id", nullable=False, index=True)
    signal_rank: int = Field(nullable=False, index=True)
    signal_type: str = Field(max_length=40, nullable=False, index=True)
    signal_category: str = Field(max_length=24, nullable=False, index=True)
    signal_status: str = Field(max_length=40, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    source_system: str = Field(max_length=40, nullable=False, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    measurement_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanAuthenticationFinding(SQLModel, table=True):
    __tablename__ = "scan_authentication_findings"
    __table_args__ = (
        SAIndex("ix_scan_auth_finding_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_finding_run_rank", "authentication_run_id", "finding_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    authentication_run_id: int = Field(foreign_key="scan_authentication_runs.id", nullable=False, index=True)
    finding_rank: int = Field(nullable=False, index=True)
    finding_type: str = Field(max_length=40, nullable=False, index=True)
    finding_status: str = Field(max_length=24, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    review_priority: str = Field(max_length=16, nullable=False, index=True)
    finding_text: str = Field(max_length=1024, nullable=False)
    source_signal_ids_json: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanAuthenticationArtifact(SQLModel, table=True):
    __tablename__ = "scan_authentication_artifacts"
    __table_args__ = (
        UniqueConstraint("authentication_run_id", "artifact_type", "artifact_checksum", name="uq_scan_auth_art_run_type_checksum"),
        SAIndex("ix_scan_auth_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_art_run_type", "authentication_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    authentication_run_id: int = Field(foreign_key="scan_authentication_runs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanAuthenticationIssue(SQLModel, table=True):
    __tablename__ = "scan_authentication_issues"
    __table_args__ = (
        SAIndex("ix_scan_auth_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_issue_run_type", "authentication_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    authentication_run_id: int = Field(foreign_key="scan_authentication_runs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanAuthenticationHistory(SQLModel, table=True):
    __tablename__ = "scan_authentication_history"
    __table_args__ = (
        SAIndex("ix_scan_auth_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_auth_hist_run_type", "authentication_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    authentication_run_id: int = Field(foreign_key="scan_authentication_runs.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
