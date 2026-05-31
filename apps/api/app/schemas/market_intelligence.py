from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    signal_type: str
    signal_source: str
    asset_type: str
    asset_id: int | None = None
    signal_value: float
    confidence_score: float
    observed_at: datetime
    created_at: datetime


class MarketSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    snapshot_uuid: str
    snapshot_date: date
    market_score: float
    bullish_signals: int
    bearish_signals: int
    neutral_signals: int
    created_at: datetime


class MarketTrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    trend_type: str
    asset_type: str
    asset_id: int | None = None
    trend_direction: str
    trend_strength: float
    confidence_score: float
    calculated_at: datetime
    created_at: datetime


class MarketObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    observation_uuid: str
    observation_type: str
    title: str
    description: str
    confidence_score: float
    created_by_agent: str
    created_at: datetime


class MarketAgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    agent_code: str
    execution_uuid: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class MarketSignalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketSignalRead]
    total_items: int
    limit: int
    offset: int


class MarketSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketSnapshotRead]
    total_items: int
    limit: int
    offset: int


class MarketTrendListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketTrendRead]
    total_items: int
    limit: int
    offset: int


class MarketObservationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketObservationRead]
    total_items: int
    limit: int
    offset: int


class MarketAgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAgentExecutionRead]
    total_items: int
    limit: int
    offset: int


class MarketSignalRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: MarketAgentExecutionRead
    created_count: int
    signals: list[MarketSignalRead] = Field(default_factory=list)


class MarketSnapshotRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: MarketAgentExecutionRead
    created_count: int
    snapshots: list[MarketSnapshotRead] = Field(default_factory=list)


class MarketTrendRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: MarketAgentExecutionRead
    created_count: int
    trends: list[MarketTrendRead] = Field(default_factory=list)


class MarketObservationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: MarketAgentExecutionRead
    created_count: int
    observations: list[MarketObservationRead] = Field(default_factory=list)


class MarketIntelligenceDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_score: float
    bullish_signals: int
    bearish_signals: int
    neutral_signals: int
    top_trends: list[MarketTrendRead] = Field(default_factory=list)
    latest_observations: list[MarketObservationRead] = Field(default_factory=list)
    agent_activity: list[MarketAgentExecutionRead] = Field(default_factory=list)
