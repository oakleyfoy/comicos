"""P36-04 deterministic liquidity engine ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InventoryLiquiditySnapshot(SQLModel, table=True):
    __tablename__ = "inventory_liquidity_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "channel",
            "evaluation_window_days",
            "snapshot_date",
            name="uq_inventory_liquidity_snapshot_signature",
        ),
        SAIndex("ix_inventory_liquidity_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_inventory_liquidity_snapshot_owner_status", "owner_user_id", "liquidity_status"),
        SAIndex("ix_inventory_liquidity_snapshot_item", "inventory_item_id"),
        SAIndex("ix_inventory_liquidity_snapshot_canonical", "canonical_comic_issue_id"),
        SAIndex("ix_inventory_liquidity_snapshot_channel", "channel"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True)
    catalog_issue_id: int | None = Field(
        default=None,
        foreign_key="catalog_issue.id",
        nullable=True,
        index=True,
    )
    channel: str | None = Field(default=None, max_length=40, nullable=True)
    liquidity_status: str = Field(max_length=24, nullable=False, index=True)
    days_on_market_median: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    days_to_sale_median: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    sell_through_rate_pct: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    stale_listing_rate_pct: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    relist_rate_pct: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    successful_sale_count: int = Field(default=0, nullable=False)
    failed_listing_count: int = Field(default=0, nullable=False)
    active_listing_count: int = Field(default=0, nullable=False)
    liquidity_confidence: str = Field(max_length=24, nullable=False, index=True)
    evaluation_window_days: int = Field(default=365, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    evidence_count: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class InventoryLiquidityEvidence(SQLModel, table=True):
    __tablename__ = "inventory_liquidity_evidence"
    __table_args__ = (
        SAIndex("ix_inventory_liquidity_evidence_snapshot_type", "liquidity_snapshot_id", "evidence_type", "id"),
        SAIndex("ix_inventory_liquidity_evidence_listing", "source_listing_id"),
        SAIndex("ix_inventory_liquidity_evidence_sale", "source_sale_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    liquidity_snapshot_id: int = Field(foreign_key="inventory_liquidity_snapshot.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=24, nullable=False, index=True)
    source_listing_id: int | None = Field(default=None, foreign_key="listing.id", nullable=True)
    source_sale_id: int | None = Field(default=None, foreign_key="sale_record.id", nullable=True)
    source_export_run_id: int | None = Field(default=None, foreign_key="listing_export_run.id", nullable=True)
    days_on_market: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    evidence_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ListingVelocitySnapshot(SQLModel, table=True):
    __tablename__ = "listing_velocity_snapshot"
    __table_args__ = (
        UniqueConstraint("listing_id", "snapshot_date", name="uq_listing_velocity_snapshot_listing_date"),
        SAIndex("ix_listing_velocity_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_listing_velocity_snapshot_listing", "listing_id"),
        SAIndex("ix_listing_velocity_snapshot_channel", "owner_user_id", "final_status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", nullable=False)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    first_activated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    sold_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    days_active: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    relist_count: int = Field(default=0, nullable=False)
    price_change_count: int = Field(default=0, nullable=False)
    final_status: str = Field(max_length=24, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ListingStalenessEvent(SQLModel, table=True):
    __tablename__ = "listing_staleness_event"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "event_type",
            "threshold_days",
            name="uq_listing_staleness_event_signature",
        ),
        SAIndex("ix_listing_staleness_event_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_listing_staleness_event_listing", "listing_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", nullable=False)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    event_type: str = Field(max_length=24, nullable=False, index=True)
    threshold_days: int = Field(nullable=False)
    days_active: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
