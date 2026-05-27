from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketIntelligenceFeedEventType = Literal[
    "INGESTION_BATCH_CREATED",
    "INGESTION_BATCH_COMPLETED",
    "NORMALIZATION_RUN_STARTED",
    "NORMALIZATION_RUN_COMPLETED",
    "SCORING_RUN_COMPLETED",
    "SIGNALS_GENERATED",
    "OPPORTUNITIES_GENERATED",
    "COUPLING_GENERATED",
    "SNAPSHOT_CREATED",
]
MarketIntelligenceFeedSeverity = Literal["INFO", "WARNING", "CRITICAL"]


class MarketIntelligenceFeedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    event_type: MarketIntelligenceFeedEventType | str
    severity: MarketIntelligenceFeedSeverity | str
    event_sequence_id: int
    ingestion_batch_id: int | None = None
    normalization_run_id: int | None = None
    scoring_run_id: int | None = None
    signal_snapshot_id: int | None = None
    opportunity_snapshot_id: int | None = None
    coupling_snapshot_id: int | None = None
    event_payload_json: dict[str, Any]
    event_checksum: str
    snapshot_date: date
    created_at: datetime


class MarketIntelligenceFeedSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    total_events: int
    latest_event_sequence_id: int
    latest_event_id: int | None = None
    latest_events_json: dict[str, Any]
    owner_timeline_json: list[dict[str, Any]]
    event_type_counts_json: dict[str, Any]
    severity_counts_json: dict[str, Any]
    activity_heatmap_json: dict[str, Any]
    failure_clustering_json: dict[str, Any]
    snapshot_checksum: str
    snapshot_date: date
    created_at: datetime


class MarketIntelligenceFeedHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    market_intelligence_feed_snapshot_id: int
    total_events: int
    latest_event_sequence_id: int
    latest_events_json: dict[str, Any]
    owner_timeline_json: list[dict[str, Any]]
    event_type_counts_json: dict[str, Any]
    severity_counts_json: dict[str, Any]
    snapshot_checksum: str
    snapshot_date: date
    created_at: datetime


class MarketIntelligenceFeedCursorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    cursor_key: str
    last_event_sequence_id: int
    last_event_id: int | None = None
    last_event_checksum: str | None = None
    snapshot_date: date
    created_at: datetime


class MarketIntelligenceFeedTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: int
    event_id: int
    event_type: MarketIntelligenceFeedEventType | str
    severity: MarketIntelligenceFeedSeverity | str
    created_at: datetime
    snapshot_date: date
    checksum: str


class MarketIntelligenceFeedTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketIntelligenceFeedTimelineItem] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketIntelligenceFeedEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketIntelligenceFeedEventRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketIntelligenceFeedSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketIntelligenceFeedSnapshotRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class MarketIntelligenceFeedReplayPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None
    cursor_key: str | None = Field(default=None, max_length=128)


class MarketIntelligenceFeedReplayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    snapshot: MarketIntelligenceFeedSnapshotRead
    history: MarketIntelligenceFeedHistoryRead
    total_events: int
    checksum_consistent: bool
    checksum_mismatches: list[int] = Field(default_factory=list)
