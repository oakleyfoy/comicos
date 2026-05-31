from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index as SAIndex, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class GradePrediction(SQLModel, table=True):
    __tablename__ = "grade_prediction"
    __table_args__ = (
        UniqueConstraint("prediction_uuid", name="uq_grade_prediction_uuid"),
        SAIndex("ix_grade_prediction_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_grade_prediction_scale_grade", "grading_scale", "predicted_grade", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    prediction_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    analysis_id: int = Field(foreign_key="scan_analysis.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    grading_scale: str = Field(max_length=24, nullable=False, index=True)
    predicted_grade: str = Field(max_length=16, nullable=False, index=True)
    grade_floor: str = Field(max_length=16, nullable=False)
    grade_ceiling: str = Field(max_length=16, nullable=False)
    confidence_score: float = Field(nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradePredictionEvidence(SQLModel, table=True):
    __tablename__ = "grade_prediction_evidence"
    __table_args__ = (SAIndex("ix_grade_prediction_evidence_prediction_created", "prediction_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    prediction_id: int = Field(foreign_key="grade_prediction.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=80, nullable=False, index=True)
    evidence_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRecommendation(SQLModel, table=True):
    __tablename__ = "grading_intelligence_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_grading_intelligence_recommendation_uuid"),
        SAIndex("ix_grading_intelligence_recommendation_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex(
            "ix_grading_intelligence_recommendation_type_status",
            "recommendation_type",
            "recommendation_status",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    prediction_id: int | None = Field(default=None, foreign_key="grade_prediction.id", nullable=True, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    recommendation_type: str = Field(max_length=32, nullable=False, index=True)
    title: str = Field(max_length=200, nullable=False)
    description: str = Field(sa_column=Column(Text, nullable=False))
    confidence_score: float = Field(nullable=False, index=True)
    priority_score: float = Field(nullable=False, index=True)
    recommendation_status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRecommendationReview(SQLModel, table=True):
    __tablename__ = "grading_intelligence_recommendation_review"
    __table_args__ = (
        SAIndex("ix_grading_intelligence_recommendation_review_rec_created", "recommendation_id", "reviewed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="grading_intelligence_recommendation.id", nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False, index=True)
    reviewed_by: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    reviewed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    review_notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class GradingRoiAnalysis(SQLModel, table=True):
    __tablename__ = "grading_intelligence_roi_analysis"
    __table_args__ = (SAIndex("ix_grading_intelligence_roi_analysis_owner_created", "owner_user_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_id: int | None = Field(
        default=None, foreign_key="grading_intelligence_recommendation.id", nullable=True, index=True
    )
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    raw_value: float = Field(nullable=False)
    expected_graded_value: float = Field(nullable=False)
    grading_cost: float = Field(nullable=False)
    expected_profit: float = Field(nullable=False)
    expected_roi_percent: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingAgentExecution(SQLModel, table=True):
    __tablename__ = "grading_intelligence_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_grading_intelligence_agent_execution_uuid"),
        SAIndex("ix_grading_intelligence_agent_execution_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_grading_intelligence_agent_execution_agent_started", "agent_code", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    analysis_id: int | None = Field(default=None, foreign_key="scan_analysis.id", nullable=True, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
