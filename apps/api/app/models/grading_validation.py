from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class GradeValidation(SQLModel, table=True):
    __tablename__ = "grade_validation"
    __table_args__ = (
        UniqueConstraint("validation_uuid", name="uq_grade_validation_uuid"),
        SAIndex("ix_grade_validation_owner_validated", "owner_user_id", "validated_at", "id"),
        SAIndex("ix_grade_validation_prediction_validated", "prediction_id", "validated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    validation_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    prediction_id: int = Field(foreign_key="grade_prediction.id", nullable=False, index=True)
    actual_grade: str = Field(max_length=16, nullable=False)
    predicted_grade: str = Field(max_length=16, nullable=False)
    variance: float = Field(nullable=False)
    validated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradeCalibrationMetric(SQLModel, table=True):
    __tablename__ = "grade_calibration_metric"
    __table_args__ = (
        SAIndex("ix_grade_calibration_metric_scale_accuracy", "grading_scale", "accuracy_score", "id"),
        SAIndex("ix_grade_calibration_metric_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    metric_date: date = Field(nullable=False, index=True)
    grading_scale: str = Field(max_length=24, nullable=False, index=True)
    total_predictions: int = Field(nullable=False)
    average_variance: float = Field(nullable=False)
    accuracy_score: float = Field(nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradePredictionOutcome(SQLModel, table=True):
    __tablename__ = "grade_prediction_outcome"
    __table_args__ = (
        UniqueConstraint("outcome_uuid", name="uq_grade_prediction_outcome_uuid"),
        SAIndex("ix_grade_prediction_outcome_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    outcome_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    recommendation_id: int | None = Field(
        default=None, foreign_key="grading_intelligence_recommendation.id", nullable=True, index=True
    )
    prediction_id: int | None = Field(default=None, foreign_key="grade_prediction.id", nullable=True, index=True)
    outcome_type: str = Field(max_length=48, nullable=False, index=True)
    outcome_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class GradingDriftEvent(SQLModel, table=True):
    __tablename__ = "grading_drift_event"
    __table_args__ = (
        UniqueConstraint("event_uuid", name="uq_grading_drift_event_uuid"),
        SAIndex("ix_grading_drift_event_type_detected", "drift_type", "detected_at", "id"),
        SAIndex("ix_grading_drift_event_owner_detected", "owner_user_id", "detected_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    event_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    drift_type: str = Field(max_length=48, nullable=False, index=True)
    drift_score: float = Field(nullable=False)
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingReliabilityMetric(SQLModel, table=True):
    __tablename__ = "grading_reliability_metric"
    __table_args__ = (
        UniqueConstraint("metric_uuid", name="uq_grading_reliability_metric_uuid"),
        SAIndex("ix_grading_reliability_metric_owner_measured", "owner_user_id", "measured_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    metric_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    reliability_type: str = Field(max_length=48, nullable=False, index=True)
    metric_score: float = Field(nullable=False)
    measured_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingValidationExecution(SQLModel, table=True):
    __tablename__ = "grading_validation_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_grading_validation_execution_uuid"),
        SAIndex("ix_grading_validation_execution_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_grading_validation_execution_agent_started", "agent_code", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_code: str = Field(max_length=64, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
