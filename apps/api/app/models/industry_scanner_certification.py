from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_SCANNER_CERTIFICATION_RESULTS = (
    "NOT_READY",
    "READY_WITH_WARNINGS",
    "APPROVED_FOR_PRODUCTION",
)


class IndustryScannerCertificationRun(SQLModel, table=True):
    __tablename__ = "industry_scanner_certification_run"
    __table_args__ = (
        SAIndex("ix_industry_scanner_cert_run_started", "started_at", "id"),
        SAIndex("ix_industry_scanner_cert_run_result", "certification_result", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="RUNNING", max_length=16, nullable=False)
    publisher_coverage_score: float = Field(default=0.0, nullable=False)
    lunar_scan_ingestion_score: float = Field(default=0.0, nullable=False)
    candidate_detection_score: float = Field(default=0.0, nullable=False)
    signal_classification_score: float = Field(default=0.0, nullable=False)
    opportunity_scoring_score: float = Field(default=0.0, nullable=False)
    dashboard_score: float = Field(default=0.0, nullable=False)
    automation_score: float = Field(default=0.0, nullable=False)
    determinism_score: float = Field(default=0.0, nullable=False)
    operations_score: float = Field(default=0.0, nullable=False)
    readiness_score: float = Field(default=0.0, nullable=False)
    certification_result: str = Field(default="NOT_READY", max_length=32, nullable=False)
    validation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
