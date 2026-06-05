"""P62-02 Buy Queue Intelligence models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P62_BUY_QUEUE_SOURCE_VERSION = "P62-02"

BUY_QUEUE_ITEM_NEW = "NEW"
BUY_QUEUE_ITEM_WATCH = "WATCH"
BUY_QUEUE_ITEM_BUY = "BUY"
BUY_QUEUE_ITEM_ORDERED = "ORDERED"
BUY_QUEUE_ITEM_SKIPPED = "SKIPPED"

BUY_QUEUE_ITEM_STATUSES = (
    BUY_QUEUE_ITEM_NEW,
    BUY_QUEUE_ITEM_WATCH,
    BUY_QUEUE_ITEM_BUY,
    BUY_QUEUE_ITEM_ORDERED,
    BUY_QUEUE_ITEM_SKIPPED,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BuyQueueSnapshot(SQLModel, table=True):
    __tablename__ = "buy_queue_snapshot"
    __table_args__ = (SAIndex("ix_buy_queue_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P62_BUY_QUEUE_SOURCE_VERSION, max_length=32, nullable=False)


class BuyQueueItem(SQLModel, table=True):
    __tablename__ = "buy_queue_item"
    __table_args__ = (
        SAIndex("ix_buy_queue_item_snapshot_priority", "snapshot_id", "priority_score", "id"),
        SAIndex("ix_buy_queue_item_owner_status", "owner_user_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="buy_queue_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_id: int | None = Field(default=None, nullable=True, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    external_catalog_issue_id: int | None = Field(
        default=None, foreign_key="external_catalog_issue.id", nullable=True, index=True
    )
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    issue_number: str = Field(default="", max_length=32, nullable=False)
    publisher: str = Field(default="", max_length=120, nullable=False)
    priority_score: float = Field(default=0.0, nullable=False, index=True)
    recommendation_score: float = Field(default=0.0, nullable=False)
    demand_score: float = Field(default=0.0, nullable=False)
    velocity_score: float = Field(default=0.0, nullable=False)
    spec_score: float = Field(default=0.0, nullable=False)
    buy_reason: str = Field(default="", sa_column=Column(Text, nullable=False))
    quantity_recommended: int = Field(default=1, nullable=False)
    estimated_cost: float = Field(default=0.0, nullable=False)
    foc_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    release_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    status: str = Field(default=BUY_QUEUE_ITEM_NEW, max_length=16, nullable=False, index=True)
