from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceOrder(SQLModel, table=True):
    __tablename__ = "marketplace_orders"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_account_id",
            "marketplace_order_identifier",
            name="uq_marketplace_order_identity",
        ),
        SAIndex("ix_mkt_order_org_ordered", "organization_id", "ordered_at", "id"),
        SAIndex(
            "ix_mkt_order_org_account_ordered",
            "organization_id",
            "marketplace_account_id",
            "ordered_at",
            "id",
        ),
        SAIndex("ix_mkt_order_org_status_ordered", "organization_id", "order_status", "ordered_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    marketplace_order_identifier: str = Field(max_length=255, nullable=False, index=True)
    marketplace_type: str = Field(max_length=32, nullable=False, index=True)
    order_status: str = Field(max_length=24, nullable=False, index=True)
    buyer_identifier: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    order_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    order_currency: str = Field(max_length=8, nullable=False, index=True)
    ordered_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    imported_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceOrderLineItem(SQLModel, table=True):
    __tablename__ = "marketplace_order_line_items"
    __table_args__ = (
        SAIndex("ix_mkt_order_line_order_created", "marketplace_order_id", "created_at", "id"),
        SAIndex(
            "ix_mkt_order_line_listing_created",
            "marketplace_listing_identifier",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_order_id: int = Field(foreign_key="marketplace_orders.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    marketplace_listing_identifier: str = Field(max_length=255, nullable=False, index=True)
    quantity: int = Field(nullable=False)
    unit_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    line_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceTransaction(SQLModel, table=True):
    __tablename__ = "marketplace_transactions"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_order_id",
            "transaction_reference",
            name="uq_marketplace_transaction_reference",
        ),
        SAIndex("ix_mkt_transaction_order_created", "marketplace_order_id", "created_at", "id"),
        SAIndex(
            "ix_mkt_transaction_org_status_created",
            "organization_id",
            "transaction_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_order_id: int = Field(foreign_key="marketplace_orders.id", nullable=False, index=True)
    transaction_type: str = Field(max_length=32, nullable=False, index=True)
    transaction_status: str = Field(max_length=24, nullable=False, index=True)
    gross_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fee_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    net_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    transaction_currency: str = Field(max_length=8, nullable=False, index=True)
    transaction_reference: str = Field(max_length=255, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceOrderEvent(SQLModel, table=True):
    __tablename__ = "marketplace_order_events"
    __table_args__ = (
        SAIndex("ix_mkt_order_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mkt_order_event_order_created", "marketplace_order_id", "created_at", "id"),
        SAIndex("ix_mkt_order_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_mkt_order_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_order_id: int | None = Field(default=None, foreign_key="marketplace_orders.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
