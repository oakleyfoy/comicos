from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


FUTURE_RELEASE_CERTIFICATION_RESULTS = ("NOT_READY", "READY_WITH_WARNINGS", "APPROVED_FOR_PRODUCTION")


class FutureReleaseCertificationRun(SQLModel, table=True):
    __tablename__ = "future_release_certification_run"
    __table_args__ = (
        SAIndex("ix_future_release_cert_run_started", "started_at", "id"),
        SAIndex("ix_future_release_cert_run_result", "certification_result", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="RUNNING", max_length=16, nullable=False)
    run_detection_score: float = Field(default=0.0, nullable=False)
    next_issue_detection_score: float = Field(default=0.0, nullable=False)
    release_matching_score: float = Field(default=0.0, nullable=False)
    foc_intelligence_score: float = Field(default=0.0, nullable=False)
    dashboard_score: float = Field(default=0.0, nullable=False)
    determinism_score: float = Field(default=0.0, nullable=False)
    operations_score: float = Field(default=0.0, nullable=False)
    readiness_score: float = Field(default=0.0, nullable=False)
    certification_result: str = Field(default="NOT_READY", max_length=32, nullable=False)
    validation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
