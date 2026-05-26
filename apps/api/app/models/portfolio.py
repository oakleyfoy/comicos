"""P38-01 deterministic portfolio registry & exposure primitives."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolio"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_portfolio_owner_user_replay_key"),
        SAIndex("ix_portfolio_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_portfolio_owner_type", "owner_user_id", "portfolio_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    name: str = Field(max_length=160, nullable=False)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    portfolio_type: str = Field(max_length=32, nullable=False, index=True)
    status: str = Field(max_length=16, nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class PortfolioItem(SQLModel, table=True):
    __tablename__ = "portfolio_item"
    __table_args__ = (
        SAIndex("ix_portfolio_item_portfolio_active", "portfolio_id", "inventory_item_id", "removed_at"),
        SAIndex("ix_portfolio_item_inventory", "inventory_item_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    allocation_role: str = Field(max_length=32, nullable=False, index=True)
    allocated_value_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    allocated_value_source: str | None = Field(default=None, max_length=24, nullable=True)
    added_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    removed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioExposureSnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_exposure_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            "exposure_type",
            "exposure_key",
            name="uq_portfolio_exposure_scope_date_replay_dimension",
        ),
        SAIndex("ix_portfolio_exposure_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_portfolio_exposure_portfolio_date", "portfolio_id", "snapshot_date", "id"),
        SAIndex("ix_portfolio_exposure_batch", "generation_batch_checksum", "id"),
        SAIndex("ix_portfolio_exposure_type_key", "exposure_type", "exposure_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    generation_scope_key: str = Field(max_length=64, nullable=False)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    generation_batch_checksum: str = Field(max_length=64, nullable=False)

    exposure_type: str = Field(max_length=32, nullable=False, index=True)
    exposure_key: str = Field(max_length=256, nullable=False)

    item_count: int = Field(default=0, nullable=False)
    total_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_cost_basis_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_realized_sales_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))

    percentage_of_portfolio_value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 8), nullable=True)
    )
    percentage_of_portfolio_count: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 8), nullable=True)
    )

    exposure_status: str = Field(max_length=24, nullable=False, index=True)

    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioExposureEvidence(SQLModel, table=True):
    __tablename__ = "portfolio_exposure_evidence"
    __table_args__ = (
        SAIndex("ix_portfolio_exposure_evidence_snapshot", "portfolio_exposure_snapshot_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_exposure_snapshot_id: int = Field(
        foreign_key="portfolio_exposure_snapshot.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=24, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioAllocationSnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_allocation_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            name="uq_portfolio_allocation_scope_date_replay",
        ),
        SAIndex("ix_portfolio_allocation_owner_date", "owner_user_id", "snapshot_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    generation_scope_key: str = Field(max_length=64, nullable=False)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    total_item_count: int = Field(default=0, nullable=False)
    total_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_cost_basis_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_realized_sales_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))

    graded_item_count: int = Field(default=0, nullable=False)
    raw_item_count: int = Field(default=0, nullable=False)
    listed_item_count: int = Field(default=0, nullable=False)
    sold_item_count: int = Field(default=0, nullable=False)
    high_liquidity_count: int = Field(default=0, nullable=False)
    low_liquidity_count: int = Field(default=0, nullable=False)
    grading_candidate_count: int = Field(default=0, nullable=False)
    sale_candidate_count: int = Field(default=0, nullable=False)
    duplicate_count: int = Field(default=0, nullable=False)
    convention_assigned_count: int = Field(default=0, nullable=False)

    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioLifecycleEvent(SQLModel, table=True):
    __tablename__ = "portfolio_lifecycle_event"
    __table_args__ = (
        SAIndex("ix_portfolio_lc_portfolio_created", "portfolio_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id", nullable=False, index=True)
    event_type: str = Field(max_length=32, nullable=False, index=True)
    metadata_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
