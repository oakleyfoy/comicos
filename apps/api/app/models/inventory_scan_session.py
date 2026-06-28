from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InventoryScanSession(SQLModel, table=True):
    __tablename__ = "inventory_scan_session"
    __table_args__ = (SAIndex("ix_inventory_scan_session_user_status", "user_id", "status"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    collection_id: int | None = Field(
        default=None,
        foreign_key="user_data_collection.id",
        nullable=True,
        index=True,
    )
    name: str = Field(max_length=255, nullable=False)
    mode: str = Field(max_length=32, nullable=False, index=True)
    source_type: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    source_name: str | None = Field(default=None, max_length=255, nullable=True)
    purchase_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    acquisition_date: date | None = Field(default=None, nullable=True)
    storage_location_id: int | None = Field(
        default=None,
        foreign_key="p79_storage_location.id",
        nullable=True,
        index=True,
    )
    box_name: str | None = Field(default=None, max_length=255, nullable=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(default="active", max_length=32, nullable=False, index=True)
    total_scanned: int = Field(default=0, nullable=False)
    total_matched: int = Field(default=0, nullable=False)
    total_unmatched: int = Field(default=0, nullable=False)
    total_accepted: int = Field(default=0, nullable=False)
    purchase_order_id: int | None = Field(default=None, foreign_key="customer_order.id", nullable=True, index=True)
    context_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class InventoryScanItem(SQLModel, table=True):
    __tablename__ = "inventory_scan_item"
    __table_args__ = (SAIndex("ix_inventory_scan_item_session_status", "session_id", "status"),)

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="inventory_scan_session.id", nullable=False, index=True)
    raw_upc: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    submitted_image_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    recognition_method: str | None = Field(default=None, max_length=32, nullable=True)
    predicted_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    predicted_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True, index=True)
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 4), nullable=True))
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    position_in_session: int | None = Field(default=None, nullable=True)
    quantity: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
