"""P36-08 deterministic operational reporting registry (append-safe; no upstream mutation)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OperationalReportRun(SQLModel, table=True):
    __tablename__ = "operational_report_run"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_operational_report_run_owner_replay"),
        SAIndex("ix_operational_report_run_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_operational_report_run_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_operational_report_run_type", "owner_user_id", "report_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    report_type: str = Field(max_length=48, nullable=False, index=True)
    status: str = Field(max_length=16, nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    generation_params_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    checksum: str | None = Field(default=None, max_length=64, nullable=True)
    csv_row_count: int = Field(default=0, nullable=False)
    failure_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OperationalReportFile(SQLModel, table=True):
    __tablename__ = "operational_report_file"
    __table_args__ = (
        SAIndex("ix_operational_report_file_run", "operational_report_run_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    operational_report_run_id: int = Field(foreign_key="operational_report_run.id", nullable=False, index=True)
    file_name: str = Field(max_length=255, nullable=False)
    storage_path: str = Field(max_length=512, nullable=False)
    file_type: str = Field(max_length=16, nullable=False)
    checksum: str = Field(max_length=64, nullable=False)
    row_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OperationalReportItem(SQLModel, table=True):
    __tablename__ = "operational_report_item"
    __table_args__ = (
        SAIndex("ix_operational_report_item_run_row", "operational_report_run_id", "row_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    operational_report_run_id: int = Field(foreign_key="operational_report_run.id", nullable=False, index=True)
    row_number: int = Field(nullable=False, ge=1)
    lineage_domain: str = Field(max_length=128, nullable=False)
    lineage_key: str = Field(max_length=256, nullable=False)
    lineage_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    row_checksum: str | None = Field(default=None, max_length=64, nullable=True)

    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
