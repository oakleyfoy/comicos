from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_SCANNER_AUTOMATION_STATUSES = ("SUCCESS", "FAILED", "NO_CHANGE", "PARTIAL")
INDUSTRY_SCANNER_AUTOMATION_TRIGGERS = ("LUNAR_REFRESH", "MANUAL", "SCHEDULED")


class IndustryScannerAutomationRun(SQLModel, table=True):
    __tablename__ = "industry_scanner_automation_run"
    __table_args__ = (
        SAIndex("ix_industry_scanner_auto_run_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_industry_scanner_auto_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_run_id: int | None = Field(default=None, foreign_key="industry_release_scan_run.id", nullable=True, index=True)
    trigger_type: str = Field(default="MANUAL", max_length=24, nullable=False, index=True)
    status: str = Field(default="SUCCESS", max_length=16, nullable=False, index=True)
    catalog_fingerprint: str = Field(default="", max_length=64, nullable=False, index=True)
    releases_scanned: int = Field(default=0, nullable=False)
    candidates_created: int = Field(default=0, nullable=False)
    signals_upserted: int = Field(default=0, nullable=False)
    scores_updated: int = Field(default=0, nullable=False)
    scan_skipped: bool = Field(default=False, nullable=False)
    runtime_ms: int = Field(default=0, nullable=False)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
