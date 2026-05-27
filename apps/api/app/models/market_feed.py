"""P39-09 deterministic market intelligence feed ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketIntelligenceFeedEvent(SQLModel, table=True):
    __tablename__ = "market_intelligence_feed_event"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "event_sequence_id",
            name="uq_market_intelligence_feed_event_owner_sequence",
        ),
        SAIndex("ix_market_intelligence_feed_event_sequence", "event_sequence_id", "id"),
        SAIndex("ix_market_intelligence_feed_event_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_market_intelligence_feed_event_type_severity", "event_type", "severity", "id"),
        SAIndex("ix_market_intelligence_feed_event_checksum", "event_checksum", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    event_sequence_id: int = Field(nullable=False, index=True)

    ingestion_batch_id: int | None = Field(default=None, nullable=True, index=True)
    normalization_run_id: int | None = Field(default=None, nullable=True, index=True)
    scoring_run_id: int | None = Field(default=None, nullable=True, index=True)
    signal_snapshot_id: int | None = Field(default=None, nullable=True, index=True)
    opportunity_snapshot_id: int | None = Field(default=None, nullable=True, index=True)
    coupling_snapshot_id: int | None = Field(default=None, nullable=True, index=True)

    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    event_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketIntelligenceFeedSnapshot(SQLModel, table=True):
    __tablename__ = "market_intelligence_feed_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "snapshot_checksum",
            name="uq_market_intelligence_feed_snapshot_signature",
        ),
        SAIndex("ix_market_intelligence_feed_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_market_intelligence_feed_snapshot_sequence",
            "latest_event_sequence_id",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    total_events: int = Field(default=0, nullable=False)
    latest_event_sequence_id: int = Field(default=0, nullable=False, index=True)
    latest_event_id: int | None = Field(default=None, nullable=True, index=True)
    latest_events_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    owner_timeline_json: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    event_type_counts_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    severity_counts_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    activity_heatmap_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    failure_clustering_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketIntelligenceFeedHistory(SQLModel, table=True):
    __tablename__ = "market_intelligence_feed_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "snapshot_checksum",
            name="uq_market_intelligence_feed_history_signature",
        ),
        SAIndex("ix_market_intelligence_feed_history_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_market_intelligence_feed_history_sequence", "latest_event_sequence_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    market_intelligence_feed_snapshot_id: int = Field(
        foreign_key="market_intelligence_feed_snapshot.id",
        nullable=False,
        index=True,
    )
    total_events: int = Field(default=0, nullable=False)
    latest_event_sequence_id: int = Field(default=0, nullable=False, index=True)
    latest_events_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    owner_timeline_json: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    event_type_counts_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    severity_counts_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketIntelligenceFeedCursor(SQLModel, table=True):
    __tablename__ = "market_intelligence_feed_cursor"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "cursor_key",
            name="uq_market_intelligence_feed_cursor_owner_key",
        ),
        SAIndex("ix_market_intelligence_feed_cursor_owner_seq", "owner_user_id", "last_event_sequence_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    cursor_key: str = Field(max_length=128, nullable=False, index=True)
    last_event_sequence_id: int = Field(default=0, nullable=False, index=True)
    last_event_id: int | None = Field(default=None, nullable=True, index=True)
    last_event_checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
