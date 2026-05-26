"""P36-03 deterministic sales ledger (realized sale truth; append-only history)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SaleRecord(SQLModel, table=True):
    __tablename__ = "sale_record"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_sale_record_owner_replay"),
        SAIndex("ix_sale_record_owner_created_at", "owner_user_id", "created_at", "id"),
        SAIndex("ix_sale_record_owner_status", "owner_user_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int | None = Field(default=None, foreign_key="listing.id", nullable=True, index=True)
    channel: str = Field(max_length=40, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    sale_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    buyer_reference: str | None = Field(default=None, max_length=255, nullable=True)
    currency: str = Field(max_length=8, nullable=False, index=True)

    gross_sale_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    item_subtotal_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    shipping_charged_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    tax_collected_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    platform_fee_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    payment_fee_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    shipping_cost_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    other_cost_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    net_proceeds_amount: Decimal = Field(
        default=0,
        sa_column=Column(Numeric(12, 2), nullable=False, default=0),
    )
    acquisition_cost_basis_amount: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    realized_profit_amount: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    realized_margin_pct: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(18, 8), nullable=True),
    )
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    recorded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    voided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class SaleRecordLineItem(SQLModel, table=True):
    __tablename__ = "sale_record_line_item"
    __table_args__ = (SAIndex("ix_sale_line_item_sale_created", "sale_record_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    sale_record_id: int = Field(foreign_key="sale_record.id", nullable=False, index=True)
    listing_id: int | None = Field(default=None, foreign_key="listing.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    quantity_sold: int = Field(nullable=False)
    unit_sale_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    line_subtotal_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    cost_basis_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    realized_profit_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SaleFinancialAdjustment(SQLModel, table=True):
    __tablename__ = "sale_financial_adjustment"
    __table_args__ = (SAIndex("ix_sale_fin_adjustment_sale_created", "sale_record_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    sale_record_id: int = Field(foreign_key="sale_record.id", nullable=False, index=True)
    adjustment_type: str = Field(max_length=40, nullable=False, index=True)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(max_length=8, nullable=False, index=True)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SaleLifecycleEvent(SQLModel, table=True):
    __tablename__ = "sale_lifecycle_event"
    __table_args__ = (
        SAIndex("ix_sale_lifecycle_event_sale_created", "sale_record_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    sale_record_id: int = Field(foreign_key="sale_record.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    prior_status: str | None = Field(default=None, max_length=24, nullable=True)
    new_status: str | None = Field(default=None, max_length=24, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
