from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Float, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_snapshot_uuid() -> str:
    return str(uuid4())


def generate_observation_uuid() -> str:
    return str(uuid4())


def generate_execution_uuid() -> str:
    return str(uuid4())


class MarketSignal(SQLModel, table=True):
    __tablename__ = "market_signal"
    __table_args__ = (
        SAIndex("ix_market_signal_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    signal_type: str = Field(max_length=80, nullable=False, index=True)
    signal_source: str = Field(max_length=80, nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int | None = Field(default=None, nullable=True, index=True)
    signal_value: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    observed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketSnapshot(SQLModel, table=True):
    __tablename__ = "market_snapshot"
    __table_args__ = (
        UniqueConstraint("snapshot_uuid", name="uq_market_snapshot_uuid"),
        SAIndex("ix_market_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_market_snapshot_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_uuid: str = Field(default_factory=generate_snapshot_uuid, max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    market_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    bullish_signals: int = Field(default=0, nullable=False)
    bearish_signals: int = Field(default=0, nullable=False)
    neutral_signals: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketTrend(SQLModel, table=True):
    __tablename__ = "market_trend"
    __table_args__ = (
        SAIndex("ix_market_trend_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    trend_type: str = Field(max_length=80, nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int | None = Field(default=None, nullable=True, index=True)
    trend_direction: str = Field(max_length=24, nullable=False, index=True)
    trend_strength: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    calculated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketObservation(SQLModel, table=True):
    __tablename__ = "market_observation"
    __table_args__ = (
        UniqueConstraint("observation_uuid", name="uq_market_observation_uuid"),
        SAIndex("ix_market_observation_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    observation_uuid: str = Field(default_factory=generate_observation_uuid, max_length=64, nullable=False, index=True)
    observation_type: str = Field(max_length=80, nullable=False, index=True)
    title: str = Field(max_length=255, nullable=False)
    description: str = Field(sa_column=Column(String, nullable=False))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    created_by_agent: str = Field(max_length=80, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAgentExecution(SQLModel, table=True):
    __tablename__ = "market_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_market_agent_execution_uuid"),
        SAIndex("ix_market_agent_execution_owner_created", "owner_user_id", "created_at", "id"),
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
