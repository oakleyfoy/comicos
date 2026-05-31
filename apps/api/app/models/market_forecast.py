from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Float, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_forecast_uuid() -> str:
    return str(uuid4())


def generate_assessment_uuid() -> str:
    return str(uuid4())


def generate_execution_uuid() -> str:
    return str(uuid4())


class MarketForecast(SQLModel, table=True):
    __tablename__ = "market_forecast"
    __table_args__ = (
        UniqueConstraint("forecast_uuid", name="uq_market_forecast_uuid"),
        SAIndex("ix_market_forecast_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    forecast_uuid: str = Field(default_factory=generate_forecast_uuid, max_length=64, nullable=False, index=True)
    forecast_type: str = Field(max_length=80, nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int | None = Field(default=None, nullable=True, index=True)
    forecast_horizon_days: int = Field(nullable=False, index=True)
    forecast_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketForecastPoint(SQLModel, table=True):
    __tablename__ = "market_forecast_point"
    __table_args__ = (
        SAIndex("ix_market_forecast_point_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    forecast_id: int = Field(foreign_key="market_forecast.id", nullable=False, index=True)
    forecast_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    projected_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketForecastConfidence(SQLModel, table=True):
    __tablename__ = "market_forecast_confidence"
    __table_args__ = (
        SAIndex("ix_market_forecast_confidence_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    forecast_id: int = Field(foreign_key="market_forecast.id", nullable=False, index=True)
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    confidence_band: str = Field(max_length=24, nullable=False, index=True)
    explanation: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketRiskAssessment(SQLModel, table=True):
    __tablename__ = "market_risk_assessment"
    __table_args__ = (
        UniqueConstraint("assessment_uuid", name="uq_market_risk_assessment_uuid"),
        SAIndex("ix_market_risk_assessment_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    assessment_uuid: str = Field(default_factory=generate_assessment_uuid, max_length=64, nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int | None = Field(default=None, nullable=True, index=True)
    risk_type: str = Field(max_length=80, nullable=False, index=True)
    risk_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ForecastAgentExecution(SQLModel, table=True):
    __tablename__ = "forecast_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_forecast_agent_execution_uuid"),
        SAIndex("ix_forecast_agent_execution_owner_created", "owner_user_id", "created_at", "id"),
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
