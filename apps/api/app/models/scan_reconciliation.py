from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanReconciliationRun(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "reconciliation_checksum", name="uq_scan_recon_run_owner_checksum"),
        SAIndex("ix_scan_recon_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_run_owner_status", "owner_user_id", "reconciliation_status", "id"),
        SAIndex("ix_scan_recon_run_scan_image", "scan_image_id", "created_at", "id"),
        SAIndex("ix_scan_recon_run_ocr_run", "ocr_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    normalization_run_id: int = Field(foreign_key="scan_normalization_run.id", nullable=False, index=True)
    boundary_run_id: int = Field(foreign_key="scan_boundary_run.id", nullable=False, index=True)
    ocr_run_id: int = Field(foreign_key="scan_ocr_run.id", nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    reconciliation_checksum: str = Field(max_length=64, nullable=False, index=True)
    reconciliation_status: str = Field(max_length=40, nullable=False, index=True)
    reconciliation_engine_version: str = Field(max_length=40, nullable=False, index=True)
    canonical_dataset_version: str = Field(max_length=64, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanReconciliationCandidate(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_candidate"
    __table_args__ = (
        SAIndex("ix_scan_recon_candidate_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_candidate_run_rank", "reconciliation_run_id", "candidate_rank", "id"),
        SAIndex("ix_scan_recon_candidate_run_conf", "reconciliation_run_id", "confidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    reconciliation_run_id: int = Field(foreign_key="scan_reconciliation_run.id", nullable=False, index=True)
    candidate_rank: int = Field(nullable=False, index=True)
    canonical_comic_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    publisher: str | None = Field(default=None, max_length=255, nullable=True)
    series_title: str | None = Field(default=None, max_length=255, nullable=True)
    issue_number: str | None = Field(default=None, max_length=64, nullable=True)
    variant_description: str | None = Field(default=None, max_length=255, nullable=True)
    publication_date: str | None = Field(default=None, max_length=32, nullable=True)
    confidence_score: float = Field(default=0.0, nullable=False, index=True)
    title_similarity_score: float = Field(default=0.0, nullable=False)
    issue_similarity_score: float = Field(default=0.0, nullable=False)
    publisher_similarity_score: float = Field(default=0.0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReconciliationDecision(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_decision"
    __table_args__ = (
        SAIndex("ix_scan_recon_decision_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_decision_run", "reconciliation_run_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    reconciliation_run_id: int = Field(foreign_key="scan_reconciliation_run.id", nullable=False, index=True)
    selected_candidate_id: int | None = Field(
        default=None,
        foreign_key="scan_reconciliation_candidate.id",
        nullable=True,
        index=True,
    )
    decision_status: str = Field(max_length=40, nullable=False, index=True)
    final_confidence_score: float = Field(default=0.0, nullable=False, index=True)
    decision_reason: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReconciliationArtifact(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_artifact"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_recon_art_run_type_checksum",
        ),
        SAIndex("ix_scan_recon_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_art_run_type", "reconciliation_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    reconciliation_run_id: int = Field(foreign_key="scan_reconciliation_run.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReconciliationIssue(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_issue"
    __table_args__ = (
        SAIndex("ix_scan_recon_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_issue_run_type", "reconciliation_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    reconciliation_run_id: int = Field(foreign_key="scan_reconciliation_run.id", nullable=False, index=True)
    issue_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReconciliationHistory(SQLModel, table=True):
    __tablename__ = "scan_reconciliation_history"
    __table_args__ = (
        SAIndex("ix_scan_recon_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_recon_hist_run_type", "reconciliation_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    reconciliation_run_id: int = Field(foreign_key="scan_reconciliation_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
