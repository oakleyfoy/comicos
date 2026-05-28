from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScanReplayRun(SQLModel, table=True):
    __tablename__ = "scan_replay_runs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_checksum", name="uq_scan_replay_run_owner_checksum"),
        SAIndex("ix_scan_replay_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_run_owner_status", "owner_user_id", "replay_status", "id"),
        SAIndex("ix_scan_replay_run_scope", "replay_scope", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_image_id: int | None = Field(default=None, foreign_key="scan_image.id", nullable=True, index=True)
    replay_scope: str = Field(max_length=40, nullable=False, index=True)
    source_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_status: str = Field(max_length=40, nullable=False, index=True)
    engine_version: str = Field(max_length=40, nullable=False, index=True)
    input_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    output_manifest_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanReplayStep(SQLModel, table=True):
    __tablename__ = "scan_replay_steps"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "phase_key", name="uq_scan_replay_step_run_phase"),
        SAIndex("ix_scan_replay_step_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_step_run_rank", "replay_run_id", "step_rank", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    step_rank: int = Field(nullable=False, index=True)
    phase_key: str = Field(max_length=48, nullable=False, index=True)
    source_record_id: int | None = Field(default=None, nullable=True, index=True)
    expected_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    observed_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    replay_step_status: str = Field(max_length=24, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReplayCheck(SQLModel, table=True):
    __tablename__ = "scan_replay_checks"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "step_id", "check_type", "expected_value", "observed_value", name="uq_scan_replay_check_run_step_type_values"),
        SAIndex("ix_scan_replay_check_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_check_run_type", "replay_run_id", "check_type", "id"),
        SAIndex("ix_scan_replay_check_step_type", "step_id", "check_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    step_id: int | None = Field(default=None, foreign_key="scan_replay_steps.id", nullable=True, index=True)
    check_type: str = Field(max_length=40, nullable=False, index=True)
    check_status: str = Field(max_length=16, nullable=False, index=True)
    expected_value: str | None = Field(default=None, max_length=2048, nullable=True)
    observed_value: str | None = Field(default=None, max_length=2048, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReplayDiscrepancy(SQLModel, table=True):
    __tablename__ = "scan_replay_discrepancies"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "step_id", "discrepancy_type", "expected_value", "observed_value", name="uq_scan_replay_disc_run_step_type_values"),
        SAIndex("ix_scan_replay_disc_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_disc_run_severity", "replay_run_id", "severity", "id"),
        SAIndex("ix_scan_replay_disc_run_type", "replay_run_id", "discrepancy_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    step_id: int | None = Field(default=None, foreign_key="scan_replay_steps.id", nullable=True, index=True)
    discrepancy_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    expected_value: str | None = Field(default=None, max_length=2048, nullable=True)
    observed_value: str | None = Field(default=None, max_length=2048, nullable=True)
    discrepancy_message: str = Field(max_length=1024, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReplayArtifact(SQLModel, table=True):
    __tablename__ = "scan_replay_artifacts"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "artifact_type", "artifact_checksum", name="uq_scan_replay_art_run_type_checksum"),
        SAIndex("ix_scan_replay_art_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_art_run_type", "replay_run_id", "artifact_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=40, nullable=False, index=True)
    storage_backend: str = Field(default="filesystem", max_length=40, nullable=False, index=True)
    storage_path: str = Field(max_length=1024, nullable=False)
    artifact_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReplayIssue(SQLModel, table=True):
    __tablename__ = "scan_replay_issues"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "issue_checksum", name="uq_scan_replay_issue_run_checksum"),
        SAIndex("ix_scan_replay_issue_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_issue_run_type", "replay_run_id", "issue_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    issue_type: str = Field(max_length=64, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    issue_message: str = Field(max_length=1024, nullable=False)
    issue_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanReplayHistory(SQLModel, table=True):
    __tablename__ = "scan_replay_history"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "event_checksum", name="uq_scan_replay_history_run_checksum"),
        SAIndex("ix_scan_replay_hist_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_replay_hist_run_type", "replay_run_id", "event_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_run_id: int = Field(foreign_key="scan_replay_runs.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_message: str = Field(max_length=512, nullable=False)
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
