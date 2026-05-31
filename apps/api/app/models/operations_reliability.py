from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class PlatformHealthCheck(SQLModel, table=True):
    __tablename__ = "platform_health_check"
    __table_args__ = (
        UniqueConstraint("check_uuid", name="uq_platform_health_check_uuid"),
        SAIndex("ix_platform_health_check_subsystem_checked", "subsystem", "checked_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    check_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    subsystem: str = Field(max_length=80, nullable=False, index=True)
    health_status: str = Field(max_length=24, nullable=False, index=True)
    health_score: float = Field(nullable=False)
    check_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    checked_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ReliabilityIssue(SQLModel, table=True):
    __tablename__ = "reliability_issue"
    __table_args__ = (
        UniqueConstraint("issue_uuid", name="uq_reliability_issue_uuid"),
        SAIndex("ix_reliability_issue_subsystem_detected", "subsystem", "detected_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    issue_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    subsystem: str = Field(max_length=80, nullable=False, index=True)
    issue_type: str = Field(max_length=80, nullable=False, index=True)
    severity: str = Field(max_length=24, nullable=False, index=True)
    issue_status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    issue_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class JobHealthMetric(SQLModel, table=True):
    __tablename__ = "job_health_metric"
    __table_args__ = (SAIndex("ix_job_health_metric_type_measured", "job_type", "measured_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    job_type: str = Field(max_length=80, nullable=False, index=True)
    total_jobs: int = Field(default=0, nullable=False)
    successful_jobs: int = Field(default=0, nullable=False)
    failed_jobs: int = Field(default=0, nullable=False)
    average_duration_ms: int = Field(default=0, nullable=False)
    measured_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class QueueHealthMetric(SQLModel, table=True):
    __tablename__ = "queue_health_metric"
    __table_args__ = (SAIndex("ix_queue_health_metric_name_measured", "queue_name", "measured_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    queue_name: str = Field(max_length=120, nullable=False, index=True)
    queued_count: int = Field(default=0, nullable=False)
    running_count: int = Field(default=0, nullable=False)
    failed_count: int = Field(default=0, nullable=False)
    measured_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecoveryRecommendation(SQLModel, table=True):
    __tablename__ = "recovery_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_recovery_recommendation_uuid"),
        SAIndex("ix_recovery_recommendation_subsystem_created", "subsystem", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    subsystem: str = Field(max_length=80, nullable=False, index=True)
    recommendation_type: str = Field(max_length=80, nullable=False, index=True)
    title: str = Field(max_length=500, nullable=False)
    description: str = Field(sa_column=Column(String, nullable=False))
    priority_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
