from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDeterminismValidationRun(SQLModel, table=True):
    __tablename__ = "market_determinism_validation_run"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "validation_checksum",
            name="uq_md_val_run_owner_checksum",
        ),
        SAIndex("ix_md_val_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_md_val_owner_status", "owner_user_id", "validation_status", "id"),
        SAIndex("ix_md_val_pipeline", "pipeline_checksum", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    validation_status: str = Field(max_length=16, nullable=False, index=True)
    validation_checksum: str = Field(max_length=64, nullable=False, index=True)
    pipeline_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    total_stages_checked: int = Field(default=0, nullable=False)
    total_invariants_checked: int = Field(default=0, nullable=False)
    total_replays_checked: int = Field(default=0, nullable=False)
    invariant_failure_count: int = Field(default=0, nullable=False)
    checksum_mismatch_count: int = Field(default=0, nullable=False)
    replay_failure_count: int = Field(default=0, nullable=False)
    ordering_failure_count: int = Field(default=0, nullable=False)
    validation_summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketDeterminismInvariant(SQLModel, table=True):
    __tablename__ = "market_determinism_invariant"
    __table_args__ = (
        SAIndex("ix_md_inv_run", "market_determinism_validation_run_id", "id"),
        SAIndex("ix_md_inv_owner_status", "owner_user_id", "invariant_status", "id"),
        SAIndex("ix_md_inv_owner_layer", "owner_user_id", "layer_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_determinism_validation_run_id: int = Field(
        foreign_key="market_determinism_validation_run.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    layer_name: str = Field(max_length=32, nullable=False, index=True)
    invariant_code: str = Field(max_length=64, nullable=False, index=True)
    invariant_status: str = Field(max_length=16, nullable=False, index=True)
    expected_value_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    actual_value_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketDeterminismChecksumAudit(SQLModel, table=True):
    __tablename__ = "market_determinism_checksum_audit"
    __table_args__ = (
        SAIndex("ix_md_chk_run", "market_determinism_validation_run_id", "id"),
        SAIndex("ix_md_chk_owner_status", "owner_user_id", "validation_status", "id"),
        SAIndex("ix_md_chk_stage", "stage_name", "upstream_stage_name", "id"),
        SAIndex("ix_md_chk_pipeline", "pipeline_checksum", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_determinism_validation_run_id: int = Field(
        foreign_key="market_determinism_validation_run.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    stage_name: str = Field(max_length=32, nullable=False, index=True)
    upstream_stage_name: str | None = Field(default=None, max_length=32, nullable=True)
    validation_status: str = Field(max_length=16, nullable=False, index=True)
    upstream_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    current_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    pipeline_checksum: str = Field(max_length=64, nullable=False, index=True)
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketDeterminismReplayAudit(SQLModel, table=True):
    __tablename__ = "market_determinism_replay_audit"
    __table_args__ = (
        SAIndex("ix_md_rep_run", "market_determinism_validation_run_id", "id"),
        SAIndex("ix_md_rep_owner_status", "owner_user_id", "replay_status", "id"),
        SAIndex("ix_md_rep_artifact", "artifact_type", "replay_status", "id"),
        SAIndex("ix_md_rep_pipeline", "pipeline_checksum", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_determinism_validation_run_id: int = Field(
        foreign_key="market_determinism_validation_run.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    artifact_type: str = Field(max_length=32, nullable=False, index=True)
    artifact_key: str = Field(max_length=128, nullable=False, index=True)
    replay_status: str = Field(max_length=16, nullable=False, index=True)
    original_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    replay_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    pipeline_checksum: str = Field(max_length=64, nullable=False, index=True)
    detail_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
