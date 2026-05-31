from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, Numeric, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_listing_uuid() -> str:
    return str(uuid4())


class MarketplaceListing(SQLModel, table=True):
    __tablename__ = "marketplace_listing"
    __table_args__ = (
        UniqueConstraint("listing_uuid", name="uq_marketplace_listing_uuid"),
        SAIndex("ix_marketplace_listing_listing_uuid", "listing_uuid"),
        SAIndex("ix_marketplace_listing_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    listing_uuid: str = Field(default_factory=generate_listing_uuid, max_length=64, nullable=False)
    listing_title: str = Field(max_length=500, nullable=False)
    listing_description: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    listing_type: str = Field(max_length=80, nullable=False)
    condition_label: str = Field(max_length=120, nullable=False)
    grade_label: str | None = Field(default=None, max_length=120, nullable=True)
    asking_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(default="USD", max_length=8, nullable=False)
    quantity: int = Field(default=1, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingVariant(SQLModel, table=True):
    __tablename__ = "marketplace_listing_variant"
    __table_args__ = (
        UniqueConstraint("listing_id", "variant_code", name="uq_marketplace_listing_variant_code"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    variant_code: str = Field(max_length=80, nullable=False)
    variant_name: str = Field(max_length=200, nullable=False)
    sku: str | None = Field(default=None, max_length=120, nullable=True)
    quantity: int = Field(default=1, nullable=False)
    price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingImage(SQLModel, table=True):
    __tablename__ = "marketplace_listing_image"
    __table_args__ = (
        UniqueConstraint("listing_id", "sort_order", name="uq_marketplace_listing_image_sort_order"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    image_url: str = Field(nullable=False)
    image_type: str = Field(max_length=80, nullable=False)
    sort_order: int = Field(default=0, nullable=False)
    is_primary: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingPrice(SQLModel, table=True):
    __tablename__ = "marketplace_listing_price"

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    price_type: str = Field(max_length=80, nullable=False)
    amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(default="USD", max_length=8, nullable=False)
    effective_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingStatusHistory(SQLModel, table=True):
    __tablename__ = "marketplace_listing_status_history"

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    previous_status: str | None = Field(default=None, max_length=24, nullable=True)
    new_status: str = Field(max_length=24, nullable=False)
    reason: str | None = Field(default=None, max_length=500, nullable=True)
    changed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingMapping(SQLModel, table=True):
    __tablename__ = "marketplace_listing_mapping"
    __table_args__ = (
        SAIndex("ix_marketplace_listing_mapping_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    marketplace_id: int = Field(foreign_key="marketplace_definition.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_account.id", nullable=True, index=True)
    external_listing_id: str | None = Field(default=None, max_length=200, nullable=True, index=True)
    external_url: str | None = Field(default=None, nullable=True)
    sync_status: str = Field(max_length=24, nullable=False, index=True)
    last_synced_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
