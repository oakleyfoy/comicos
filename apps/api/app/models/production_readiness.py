from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class ProductionReadinessCheck(SQLModel, table=True):
    __tablename__ = "production_readiness_check"
    __table_args__ = (
        UniqueConstraint("check_uuid", name="uq_production_readiness_check_uuid"),
        SAIndex("ix_production_readiness_check_subsystem_checked", "subsystem", "checked_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    check_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    check_name: str = Field(max_length=120, nullable=False, index=True)
    subsystem: str = Field(max_length=80, nullable=False, index=True)
    check_status: str = Field(max_length=24, nullable=False, index=True)
    check_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    checked_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ProductionCertification(SQLModel, table=True):
    __tablename__ = "production_certification"
    __table_args__ = (
        UniqueConstraint("certification_uuid", name="uq_production_certification_uuid"),
        SAIndex("ix_production_certification_status_certified", "certification_status", "certified_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    certification_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    certification_status: str = Field(max_length=32, nullable=False, index=True)
    readiness_score: float = Field(nullable=False)
    certification_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    certified_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ReadinessChecklistItem(SQLModel, table=True):
    __tablename__ = "readiness_checklist_item"
    __table_args__ = (SAIndex("ix_readiness_checklist_category_validated", "checklist_category", "validated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    checklist_category: str = Field(max_length=80, nullable=False, index=True)
    item_name: str = Field(max_length=120, nullable=False, index=True)
    item_status: str = Field(max_length=24, nullable=False, index=True)
    validation_notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    validated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GoLiveAssessment(SQLModel, table=True):
    __tablename__ = "go_live_assessment"
    __table_args__ = (
        UniqueConstraint("assessment_uuid", name="uq_go_live_assessment_uuid"),
        SAIndex("ix_go_live_assessment_status_assessed", "assessment_status", "assessed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    assessment_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    assessment_status: str = Field(max_length=32, nullable=False, index=True)
    overall_score: float = Field(nullable=False)
    assessment_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    assessed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


GO_LIVE_RESULTS = ("NOT_READY", "READY_WITH_WARNINGS", "GO_LIVE_APPROVED")
PRODUCTION_READINESS_HEALTH = ("HEALTHY", "WARNING", "UNHEALTHY")


class ProductionReadinessRun(SQLModel, table=True):
    __tablename__ = "production_readiness_run"
    __table_args__ = (
        SAIndex("ix_production_readiness_run_started", "started_at", "id"),
        SAIndex("ix_production_readiness_run_go_live", "go_live_result", "id"),
        SAIndex("ix_production_readiness_run_health", "health_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="RUNNING", max_length=16, nullable=False)

    import_health_score: float = Field(default=0.0, nullable=False)
    inventory_health_score: float = Field(default=0.0, nullable=False)
    recommendation_health_score: float = Field(default=0.0, nullable=False)
    dashboard_health_score: float = Field(default=0.0, nullable=False)
    automation_health_score: float = Field(default=0.0, nullable=False)
    workflow_health_score: float = Field(default=0.0, nullable=False)
    operations_health_score: float = Field(default=0.0, nullable=False)

    readiness_score: float = Field(default=0.0, nullable=False)
    go_live_result: str = Field(default="NOT_READY", max_length=32, nullable=False)
    health_status: str = Field(default="UNHEALTHY", max_length=16, nullable=False)
    validation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
