from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

SOURCE_VERSION = "P51-03"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDemandProfile(SQLModel, table=True):
    __tablename__ = "market_demand_profile"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_name", name="uq_market_demand_profile_entity"),
        SAIndex("ix_market_demand_profile_demand", "demand_score", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=24, nullable=False, index=True)
    entity_id: int = Field(default=0, nullable=False, index=True)
    entity_name: str = Field(max_length=160, nullable=False, index=True)
    demand_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    source_version: str = Field(default=SOURCE_VERSION, max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketDemandSignal(SQLModel, table=True):
    __tablename__ = "market_demand_signal"
    __table_args__ = (SAIndex("ix_market_demand_signal_profile", "profile_id", "signal_type", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="market_demand_profile.id", nullable=False, index=True)
    signal_type: str = Field(max_length=48, nullable=False, index=True)
    signal_strength: float = Field(default=0.0, nullable=False)
    signal_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class HistoricalPerformanceSignal(SQLModel, table=True):
    __tablename__ = "historical_performance_signal"
    __table_args__ = (SAIndex("ix_historical_performance_entity", "entity_type", "entity_name", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=24, nullable=False, index=True)
    entity_name: str = Field(max_length=160, nullable=False, index=True)
    performance_type: str = Field(max_length=48, nullable=False, index=True)
    performance_score: float = Field(default=0.0, nullable=False)
    confidence_score: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectorDemandScore(SQLModel, table=True):
    __tablename__ = "collector_demand_score"
    __table_args__ = (SAIndex("ix_collector_demand_entity", "entity_type", "entity_name", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=24, nullable=False, index=True)
    entity_name: str = Field(max_length=160, nullable=False, index=True)
    collector_score: float = Field(default=0.0, nullable=False, index=True)
    liquidity_score: float = Field(default=0.0, nullable=False)
    long_term_score: float = Field(default=0.0, nullable=False)
    volatility_score: float = Field(default=0.0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
