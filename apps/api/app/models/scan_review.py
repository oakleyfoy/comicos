from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanReviewSession(SQLModel, table=True):
    __tablename__ = "scan_review_session"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "review_checksum", name="uq_scan_review_session_owner_checksum"),
        SAIndex("ix_scan_review_session_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_session_owner_status", "owner_user_id", "review_status", "id"),
        SAIndex("ix_scan_review_session_scan_image", "scan_image_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int = Field(foreign_key="scan_image.id", nullable=False, index=True)
    visual_evidence_run_id: int | None = Field(default=None, foreign_key="scan_visual_evidence_run.id", nullable=True, index=True)
    grading_assistance_run_id: int | None = Field(default=None, foreign_key="scan_grading_assistance_run.id", nullable=True, index=True)
    reconciliation_run_id: int | None = Field(default=None, foreign_key="scan_reconciliation_run.id", nullable=True, index=True)
    review_status: str = Field(max_length=32, nullable=False, index=True)
    review_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    reviewer_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanReviewDecision(SQLModel, table=True):
    __tablename__ = "scan_review_decision"
    __table_args__ = (
        SAIndex("ix_scan_review_decision_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_decision_session_type", "review_session_id", "decision_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    decision_type: str = Field(max_length=48, nullable=False, index=True)
    decision_status: str = Field(max_length=24, nullable=False, index=True)
    decision_value: str = Field(max_length=255, nullable=False)
    confidence_score: float | None = Field(default=None, nullable=True, index=True)
    reason_text: str = Field(max_length=1024, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReviewNote(SQLModel, table=True):
    __tablename__ = "scan_review_note"
    __table_args__ = (
        SAIndex("ix_scan_review_note_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_note_session_type", "review_session_id", "note_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    note_type: str = Field(max_length=32, nullable=False, index=True)
    note_text: str = Field(max_length=4000, nullable=False)
    source_system: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReviewEvidenceAction(SQLModel, table=True):
    __tablename__ = "scan_review_evidence_action"
    __table_args__ = (
        SAIndex("ix_scan_review_action_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_action_session_source", "review_session_id", "source_system", "source_record_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    source_system: str = Field(max_length=40, nullable=False, index=True)
    source_record_id: int = Field(nullable=False, index=True)
    action_type: str = Field(max_length=32, nullable=False, index=True)
    action_status: str = Field(max_length=16, nullable=False, index=True)
    reason_text: str = Field(max_length=1024, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReviewArtifact(SQLModel, table=True):
    __tablename__ = "scan_review_artifact"
    __table_args__ = (
        UniqueConstraint("review_session_id", "artifact_type", "artifact_checksum", name="uq_scan_review_artifact_session_type_checksum"),
        SAIndex("ix_scan_review_artifact_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_artifact_session_type", "review_session_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReviewIssue(SQLModel, table=True):
    __tablename__ = "scan_review_issue"
    __table_args__ = (
        SAIndex("ix_scan_review_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_issue_session_type", "review_session_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=512, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReviewHistory(SQLModel, table=True):
    __tablename__ = "scan_review_history"
    __table_args__ = (
        SAIndex("ix_scan_review_history_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_review_history_session_type", "review_session_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    review_session_id: int = Field(foreign_key="scan_review_session.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
