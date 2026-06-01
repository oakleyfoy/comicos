from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_RELEASE_SCAN_STATUSES = ("RUNNING", "SUCCESS", "FAILED")


class IndustryReleaseScanRun(SQLModel, table=True):
    __tablename__ = "industry_release_scan_run"
    __table_args__ = (
        SAIndex("ix_industry_release_scan_run_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_industry_release_scan_run_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    status: str = Field(default="RUNNING", max_length=16, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    releases_scanned: int = Field(default=0, nullable=False)
    candidates_created: int = Field(default=0, nullable=False)
    candidates_total: int = Field(default=0, nullable=False)
    publishers_included: int = Field(default=0, nullable=False)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IndustryReleaseCandidate(SQLModel, table=True):
    __tablename__ = "industry_release_candidate"
    __table_args__ = (
        UniqueConstraint("scan_run_id", "release_id", name="uq_industry_release_candidate_run_release"),
        SAIndex("ix_industry_release_candidate_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_industry_release_candidate_run_series", "scan_run_id", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_run_id: int = Field(foreign_key="industry_release_scan_run.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    publisher_code: str = Field(max_length=32, nullable=False, index=True)
    publisher_name: str = Field(max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    issue_number: str = Field(max_length=32, nullable=False)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    variant_count: int = Field(default=0, nullable=False)
    monitoring_status: str = Field(default="MONITOR", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
