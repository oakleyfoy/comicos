"""P36-06 deterministic listing intelligence ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ListingIntelligenceSnapshot(SQLModel, table=True):
    __tablename__ = "listing_intelligence_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "listing_id",
            "snapshot_date",
            name="uq_listing_intelligence_snapshot_listing_date",
        ),
        SAIndex("ix_listing_intelligence_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_listing_intelligence_snapshot_owner_status", "owner_user_id", "intelligence_status"),
        SAIndex("ix_listing_intelligence_snapshot_listing", "listing_id"),
        SAIndex("ix_listing_intelligence_snapshot_inventory", "inventory_item_id"),
        SAIndex("ix_listing_intelligence_snapshot_channel", "channel"),
        SAIndex("ix_listing_intelligence_snapshot_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False)
    listing_id: int = Field(foreign_key="listing.id", nullable=False)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True)
    catalog_issue_id: int | None = Field(
        default=None,
        foreign_key="catalog_issue.id",
        nullable=True,
        index=True,
    )
    channel: str | None = Field(default=None, max_length=40, nullable=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    intelligence_status: str = Field(max_length=24, nullable=False)
    completeness_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    image_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    title_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    description_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    pricing_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    export_readiness_score: Decimal = Field(sa_column=Column(Numeric(6, 2), nullable=False))
    sale_outcome_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    stale_risk_flag: bool = Field(default=False, nullable=False, index=True)

    missing_required_fields_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    warning_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evidence_count: int = Field(default=0, nullable=False)
    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ListingIntelligenceEvidence(SQLModel, table=True):
    __tablename__ = "listing_intelligence_evidence"
    __table_args__ = (
        SAIndex("ix_listing_intelligence_evidence_snapshot_key", "intelligence_snapshot_id", "evidence_type", "evidence_key", "id"),
        SAIndex("ix_listing_intelligence_evidence_listing", "source_listing_id"),
        SAIndex("ix_listing_intelligence_evidence_export_run", "source_export_run_id"),
        SAIndex("ix_listing_intelligence_evidence_sale", "source_sale_id"),
        SAIndex("ix_listing_intelligence_evidence_liquidity", "source_liquidity_snapshot_id"),
        SAIndex("ix_listing_intelligence_evidence_convention", "source_convention_event_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    intelligence_snapshot_id: int = Field(foreign_key="listing_intelligence_snapshot.id", nullable=False)
    evidence_type: str = Field(max_length=24, nullable=False)
    source_listing_id: int | None = Field(default=None, foreign_key="listing.id", nullable=True)
    source_export_run_id: int | None = Field(default=None, foreign_key="listing_export_run.id", nullable=True)
    source_sale_id: int | None = Field(default=None, foreign_key="sale_record.id", nullable=True)
    source_liquidity_snapshot_id: int | None = Field(default=None, foreign_key="inventory_liquidity_snapshot.id", nullable=True)
    source_convention_event_id: int | None = Field(default=None, foreign_key="convention_event.id", nullable=True)
    evidence_key: str = Field(max_length=128, nullable=False)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ListingCompletenessCheck(SQLModel, table=True):
    __tablename__ = "listing_completeness_check"
    __table_args__ = (
        UniqueConstraint(
            "intelligence_snapshot_id",
            "check_key",
            name="uq_listing_completeness_check_snapshot_key",
        ),
        SAIndex("ix_listing_completeness_check_snapshot", "intelligence_snapshot_id", "id"),
        SAIndex("ix_listing_completeness_check_owner_listing", "owner_user_id", "listing_id"),
        SAIndex("ix_listing_completeness_check_status", "owner_user_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    intelligence_snapshot_id: int = Field(foreign_key="listing_intelligence_snapshot.id", nullable=False)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False)
    listing_id: int = Field(foreign_key="listing.id", nullable=False)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    status: str = Field(max_length=16, nullable=False)
    check_key: str = Field(max_length=40, nullable=False)
    message: str = Field(sa_column=Column(Text, nullable=False))
    severity: str = Field(max_length=16, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ListingChannelPerformanceSnapshot(SQLModel, table=True):
    __tablename__ = "listing_channel_performance_snapshot"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "channel", "snapshot_date", name="uq_listing_channel_perf_signature"),
        SAIndex("ix_listing_channel_perf_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_listing_channel_perf_owner_channel", "owner_user_id", "channel"),
        SAIndex("ix_listing_channel_perf_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False)
    channel: str = Field(max_length=40, nullable=False)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    total_listings: int = Field(default=0, nullable=False)
    active_listings: int = Field(default=0, nullable=False)
    sold_listings: int = Field(default=0, nullable=False)
    cancelled_listings: int = Field(default=0, nullable=False)
    exported_count: int = Field(default=0, nullable=False)
    sales_count: int = Field(default=0, nullable=False)
    gross_sales_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    net_proceeds_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    median_days_to_sale: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    stale_listing_count: int = Field(default=0, nullable=False)
    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
