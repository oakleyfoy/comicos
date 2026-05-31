from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


FINAL_CERTIFICATION_RESULTS = ("NOT_READY", "READY_WITH_WARNINGS", "APPROVED_FOR_PRODUCTION")
FINAL_HEALTH_STATUSES = ("HEALTHY", "WARNING", "UNHEALTHY")


class FinalPlatformCertificationRun(SQLModel, table=True):
    __tablename__ = "final_platform_certification_run"
    __table_args__ = (
        SAIndex("ix_final_platform_cert_run_started", "started_at", "id"),
        SAIndex("ix_final_platform_cert_run_result", "certification_result", "id"),
        SAIndex("ix_final_platform_cert_run_health", "health_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="RUNNING", max_length=16, nullable=False)

    release_intelligence_score: float = Field(default=0.0, nullable=False)
    recommendation_intelligence_score: float = Field(default=0.0, nullable=False)
    pull_list_score: float = Field(default=0.0, nullable=False)
    purchase_score: float = Field(default=0.0, nullable=False)
    portfolio_score: float = Field(default=0.0, nullable=False)
    acquisition_score: float = Field(default=0.0, nullable=False)
    exit_score: float = Field(default=0.0, nullable=False)
    unified_intelligence_score: float = Field(default=0.0, nullable=False)
    daily_action_score: float = Field(default=0.0, nullable=False)
    cross_system_score: float = Field(default=0.0, nullable=False)
    executive_dashboard_score: float = Field(default=0.0, nullable=False)
    determinism_score: float = Field(default=0.0, nullable=False)
    operations_score: float = Field(default=0.0, nullable=False)

    readiness_score: float = Field(default=0.0, nullable=False)
    certification_result: str = Field(default="NOT_READY", max_length=32, nullable=False)
    health_status: str = Field(default="UNHEALTHY", max_length=16, nullable=False)
    validation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
