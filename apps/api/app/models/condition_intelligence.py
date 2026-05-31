from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class ScanAnalysis(SQLModel, table=True):
    __tablename__ = "scan_analysis"
    __table_args__ = (
        UniqueConstraint("analysis_uuid", name="uq_scan_analysis_uuid"),
        SAIndex("ix_scan_analysis_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_scan_analysis_status_created", "analysis_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analysis_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    front_image_id: int | None = Field(default=None, foreign_key="scan_image.id", nullable=True, index=True)
    back_image_id: int | None = Field(default=None, foreign_key="scan_image.id", nullable=True, index=True)
    analysis_status: str = Field(default="PENDING", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ScanQualityAssessment(SQLModel, table=True):
    __tablename__ = "scan_quality_assessment"
    __table_args__ = (SAIndex("ix_scan_quality_assessment_analysis_created", "analysis_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    image_quality_score: float = Field(nullable=False)
    resolution_score: float = Field(nullable=False)
    alignment_score: float = Field(nullable=False)
    glare_score: float = Field(nullable=False)
    crop_score: float = Field(nullable=False)
    quality_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConditionProfile(SQLModel, table=True):
    __tablename__ = "condition_profile"
    __table_args__ = (SAIndex("ix_condition_profile_analysis_created", "analysis_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    overall_condition_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConditionDefect(SQLModel, table=True):
    __tablename__ = "condition_defect"
    __table_args__ = (
        SAIndex("ix_condition_defect_analysis_created", "analysis_id", "created_at", "id"),
        SAIndex("ix_condition_defect_type_created", "defect_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    defect_type: str = Field(max_length=80, nullable=False, index=True)
    defect_location: str = Field(max_length=120, nullable=False, index=True)
    defect_severity: str = Field(max_length=24, nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConditionSubgrade(SQLModel, table=True):
    __tablename__ = "condition_subgrade"
    __table_args__ = (
        SAIndex("ix_condition_subgrade_analysis_created", "analysis_id", "created_at", "id"),
        SAIndex("ix_condition_subgrade_type_created", "subgrade_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    subgrade_type: str = Field(max_length=32, nullable=False, index=True)
    score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConditionAgentExecution(SQLModel, table=True):
    __tablename__ = "condition_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_condition_agent_execution_uuid"),
        SAIndex("ix_condition_agent_execution_analysis_started", "analysis_id", "started_at", "id"),
        SAIndex("ix_condition_agent_execution_agent_started", "agent_code", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
