from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuickSale(SQLModel, table=True):
    __tablename__ = "quick_sales"
    __table_args__ = (
        UniqueConstraint("organization_id", "sale_identifier", name="uq_quick_sale_org_identifier"),
        SAIndex("ix_quick_sale_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_quick_sale_org_status_created", "organization_id", "sale_status", "created_at", "id"),
        SAIndex("ix_quick_sale_org_source_created", "organization_id", "sale_source", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    convention_session_id: int | None = Field(default=None, foreign_key="convention_sessions.id", nullable=True, index=True)
    mobile_device_id: int | None = Field(default=None, foreign_key="mobile_devices.id", nullable=True, index=True)
    sale_identifier: str = Field(max_length=128, nullable=False, index=True)
    sale_status: str = Field(max_length=24, nullable=False, index=True)
    buyer_label: str | None = Field(default=None, max_length=200, nullable=True)
    subtotal_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")),
    )
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")),
    )
    total_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")),
    )
    currency: str = Field(default="USD", max_length=8, nullable=False)
    sale_source: str = Field(max_length=24, nullable=False, index=True)
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    voided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class QuickSaleLineItem(SQLModel, table=True):
    __tablename__ = "quick_sale_line_items"
    __table_args__ = (
        SAIndex("ix_quick_sale_line_item_sale_created", "quick_sale_id", "created_at", "id"),
        SAIndex("ix_quick_sale_line_item_org_status_created", "organization_id", "line_status", "created_at", "id"),
        SAIndex("ix_quick_sale_line_item_org_inventory_created", "organization_id", "inventory_item_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    quick_sale_id: int = Field(foreign_key="quick_sales.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    offline_inventory_record_id: int | None = Field(
        default=None,
        foreign_key="offline_inventory_records.id",
        nullable=True,
        index=True,
    )
    marketplace_listing_draft_id: int | None = Field(
        default=None,
        foreign_key="marketplace_listing_drafts.id",
        nullable=True,
        index=True,
    )
    quantity: int = Field(nullable=False)
    unit_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0.00")),
    )
    line_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    line_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class QuickSalePayment(SQLModel, table=True):
    __tablename__ = "quick_sale_payments"
    __table_args__ = (
        SAIndex("ix_quick_sale_payment_sale_created", "quick_sale_id", "created_at", "id"),
        SAIndex("ix_quick_sale_payment_org_status_created", "organization_id", "payment_status", "created_at", "id"),
        SAIndex("ix_quick_sale_payment_org_method_created", "organization_id", "payment_method", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    quick_sale_id: int = Field(foreign_key="quick_sales.id", nullable=False, index=True)
    payment_method: str = Field(max_length=32, nullable=False, index=True)
    payment_status: str = Field(max_length=24, nullable=False, index=True)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(default="USD", max_length=8, nullable=False)
    payment_reference: str | None = Field(default=None, max_length=255, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class QuickSaleEvent(SQLModel, table=True):
    __tablename__ = "quick_sale_events"
    __table_args__ = (
        SAIndex("ix_quick_sale_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_quick_sale_event_sale_created", "quick_sale_id", "created_at", "id"),
        SAIndex("ix_quick_sale_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    quick_sale_id: int | None = Field(default=None, foreign_key="quick_sales.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
