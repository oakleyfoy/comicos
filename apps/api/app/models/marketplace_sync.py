from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_reservation_uuid() -> str:
    return str(uuid4())


def generate_order_uuid() -> str:
    return str(uuid4())


def generate_plan_uuid() -> str:
    return str(uuid4())


class MarketplaceInventoryReservation(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_reservation"
    __table_args__ = (
        UniqueConstraint("reservation_uuid", name="uq_marketplace_inventory_reservation_uuid"),
        SAIndex("ix_marketplace_inventory_reservation_reservation_uuid", "reservation_uuid"),
        SAIndex("ix_marketplace_inventory_reservation_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    reservation_uuid: str = Field(default_factory=generate_reservation_uuid, max_length=64, nullable=False)
    reservation_type: str = Field(max_length=40, nullable=False)
    quantity_reserved: int = Field(nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    source: str = Field(max_length=80, nullable=False)
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    released_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceInventoryAvailability(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_availability"
    __table_args__ = (
        SAIndex("ix_marketplace_inventory_availability_created_at", "calculated_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    total_quantity: int = Field(nullable=False)
    reserved_quantity: int = Field(nullable=False)
    available_quantity: int = Field(nullable=False)
    sold_quantity: int = Field(nullable=False)
    calculated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceOrder(SQLModel, table=True):
    __tablename__ = "marketplace_order"
    __table_args__ = (
        UniqueConstraint("order_uuid", name="uq_marketplace_order_uuid"),
        SAIndex("ix_marketplace_order_order_uuid", "order_uuid"),
        SAIndex("ix_marketplace_order_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    marketplace_id: int | None = Field(default=None, foreign_key="marketplace_definition.id", nullable=True, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_account.id", nullable=True, index=True)
    order_uuid: str = Field(default_factory=generate_order_uuid, max_length=64, nullable=False)
    external_order_id: str | None = Field(default=None, max_length=200, nullable=True, index=True)
    order_status: str = Field(max_length=24, nullable=False, index=True)
    buyer_name: str | None = Field(default=None, max_length=200, nullable=True)
    buyer_email: str | None = Field(default=None, max_length=320, nullable=True)
    subtotal_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    shipping_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    tax_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    total_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(max_length=8, nullable=False)
    ordered_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceOrderItem(SQLModel, table=True):
    __tablename__ = "marketplace_order_item"
    __table_args__ = (
        SAIndex("ix_marketplace_order_item_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="marketplace_order.id", nullable=False, index=True)
    listing_id: int | None = Field(default=None, foreign_key="marketplace_listing.id", nullable=True, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    external_item_id: str | None = Field(default=None, max_length=200, nullable=True)
    title: str = Field(max_length=500, nullable=False)
    quantity: int = Field(nullable=False)
    unit_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    total_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    item_status: str = Field(max_length=24, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceOrderEvent(SQLModel, table=True):
    __tablename__ = "marketplace_order_event"
    __table_args__ = (
        SAIndex("ix_marketplace_order_event_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="marketplace_order.id", nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceInventorySyncPlan(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_sync_plan"
    __table_args__ = (
        UniqueConstraint("plan_uuid", name="uq_marketplace_inventory_sync_plan_uuid"),
        SAIndex("ix_marketplace_inventory_sync_plan_plan_uuid", "plan_uuid"),
        SAIndex("ix_marketplace_inventory_sync_plan_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    plan_uuid: str = Field(default_factory=generate_plan_uuid, max_length=64, nullable=False)
    plan_type: str = Field(max_length=40, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceInventorySyncPlanItem(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_sync_plan_item"
    __table_args__ = (
        SAIndex("ix_marketplace_inventory_sync_plan_item_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="marketplace_inventory_sync_plan.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    marketplace_id: int | None = Field(default=None, foreign_key="marketplace_definition.id", nullable=True, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_account.id", nullable=True, index=True)
    current_available_quantity: int = Field(nullable=False)
    target_available_quantity: int = Field(nullable=False)
    action_type: str = Field(max_length=32, nullable=False)
    reason: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
