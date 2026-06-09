from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RetailerAccount(SQLModel, table=True):
    __tablename__ = "retailer_account"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    retailer: str = Field(max_length=32, nullable=False, index=True)
    display_name: str | None = Field(default=None, max_length=200)
    username: str = Field(max_length=320, nullable=False)
    encrypted_password: str = Field(max_length=4096, nullable=False)
    credential_version: int = Field(default=1, nullable=False)
    status: str = Field(default="connected", max_length=32, nullable=False, index=True)
    sync_enabled: bool = Field(default=False, nullable=False)
    last_sync_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_success_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_error: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class RetailerSyncRun(SQLModel, table=True):
    __tablename__ = "retailer_sync_run"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    retailer_account_id: int = Field(foreign_key="retailer_account.id", nullable=False, index=True)
    retailer: str = Field(max_length=32, nullable=False, index=True)
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    started_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    finished_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    orders_seen: int = Field(default=0, nullable=False)
    orders_imported: int = Field(default=0, nullable=False)
    items_seen: int = Field(default=0, nullable=False)
    items_imported: int = Field(default=0, nullable=False)
    items_updated: int = Field(default=0, nullable=False)
    errors_count: int = Field(default=0, nullable=False)
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, max_length=1024)


class RetailerOrderSnapshot(SQLModel, table=True):
    __tablename__ = "retailer_order_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "retailer",
            "retailer_order_number",
            name="uq_retailer_order_snapshot_identity",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    retailer_account_id: int = Field(foreign_key="retailer_account.id", nullable=False, index=True)
    retailer: str = Field(max_length=32, nullable=False, index=True)
    retailer_order_number: str = Field(max_length=128, nullable=False, index=True)
    order_date: date | None = Field(default=None, nullable=True)
    order_status: str | None = Field(default=None, max_length=128)
    order_total: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    source_url: str | None = Field(default=None, max_length=2048)
    raw_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class RetailerOrderItemSnapshot(SQLModel, table=True):
    __tablename__ = "retailer_order_item_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    retailer_order_snapshot_id: int = Field(
        foreign_key="retailer_order_snapshot.id", nullable=False, index=True
    )
    retailer: str = Field(max_length=32, nullable=False, index=True)
    retailer_order_number: str = Field(max_length=128, nullable=False, index=True)
    retailer_item_id: str | None = Field(default=None, max_length=128, index=True)
    product_url: str | None = Field(default=None, max_length=2048)
    image_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    title: str = Field(max_length=500, nullable=False)
    publisher: str | None = Field(default=None, max_length=200)
    issue_number: str | None = Field(default=None, max_length=64)
    cover_name: str | None = Field(default=None, max_length=255)
    variant_type: str | None = Field(default=None, max_length=255)
    cover_artist: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, nullable=False)
    unit_price: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    total_price: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    item_status: str | None = Field(default=None, max_length=128)
    shipped_qty: int | None = Field(default=None)
    backordered_qty: int | None = Field(default=None)
    unavailable_qty: int | None = Field(default=None)
    returned_qty: int | None = Field(default=None)
    release_date: date | None = Field(default=None, nullable=True)
    raw_item_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
