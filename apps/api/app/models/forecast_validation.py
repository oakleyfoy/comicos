from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Float, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_validation_uuid() -> str:
    return str(uuid4())


def generate_event_uuid() -> str:
    return str(uuid4())


def generate_outcome_uuid() -> str:
    return str(uuid4())


def generate_execution_uuid() -> str:
    return str(uuid4())


class ForecastValidation(SQLModel, table=True):
    __tablename__ = "forecast_validation"
    __table_args__ = (
        UniqueConstraint("validation_uuid", name="uq_forecast_validation_uuid"),
        SAIndex("ix_forecast_validation_owner_validated", "owner_user_id", "validated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    validation_uuid: str = Field(default_factory=generate_validation_uuid, max_length=64, nullable=False, index=True)
    forecast_id: int = Field(foreign_key="market_forecast.id", nullable=False, index=True)
    validation_type: str = Field(max_length=80, nullable=False, index=True)
    predicted_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    actual_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    variance_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    variance_percent: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    validated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ForecastAccuracyMetric(SQLModel, table=True):
    __tablename__ = "forecast_accuracy_metric"
    __table_args__ = (
        SAIndex("ix_forecast_accuracy_metric_owner_date", "owner_user_id", "metric_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    metric_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    forecast_type: str = Field(max_length=80, nullable=False, index=True)
    forecast_horizon_days: int = Field(nullable=False, index=True)
    total_forecasts: int = Field(default=0, nullable=False)
    average_error: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    average_accuracy: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ForecastDriftEvent(SQLModel, table=True):
    __tablename__ = "forecast_drift_event"
    __table_args__ = (
        UniqueConstraint("event_uuid", name="uq_forecast_drift_event_uuid"),
        SAIndex("ix_forecast_drift_event_owner_detected", "owner_user_id", "detected_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    event_uuid: str = Field(default_factory=generate_event_uuid, max_length=64, nullable=False, index=True)
    forecast_type: str = Field(max_length=80, nullable=False, index=True)
    drift_type: str = Field(max_length=80, nullable=False, index=True)
    drift_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SignalQualityMetric(SQLModel, table=True):
    __tablename__ = "signal_quality_metric"
    __table_args__ = (
        SAIndex("ix_signal_quality_metric_owner_measured", "owner_user_id", "measured_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    signal_type: str = Field(max_length=80, nullable=False, index=True)
    signal_source: str = Field(max_length=80, nullable=False, index=True)
    quality_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    completeness_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    consistency_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    measured_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ForecastOutcome(SQLModel, table=True):
    __tablename__ = "forecast_outcome"
    __table_args__ = (
        UniqueConstraint("outcome_uuid", name="uq_forecast_outcome_uuid"),
        SAIndex("ix_forecast_outcome_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    outcome_uuid: str = Field(default_factory=generate_outcome_uuid, max_length=64, nullable=False, index=True)
    recommendation_id: int | None = Field(default=None, foreign_key="dealer_recommendation.id", nullable=True, index=True)
    forecast_id: int | None = Field(default=None, foreign_key="market_forecast.id", nullable=True, index=True)
    outcome_type: str = Field(max_length=80, nullable=False, index=True)
    outcome_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ForecastValidationExecution(SQLModel, table=True):
    __tablename__ = "forecast_validation_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_forecast_validation_execution_uuid"),
        SAIndex("ix_forecast_validation_execution_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_execution_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
