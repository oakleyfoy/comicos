from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EbayCompRecord(SQLModel, table=True):
    __tablename__ = "ebay_comp_record"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "provider",
            "provider_listing_id",
            name="uq_ebay_comp_owner_provider_listing",
        ),
        SAIndex("ix_ebay_comp_owner_imported", "owner_user_id", "imported_at", "id"),
        SAIndex("ix_ebay_comp_provider_listing", "provider", "provider_listing_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    provider: str = Field(default="EBAY", max_length=32, nullable=False, index=True)
    provider_listing_id: str = Field(max_length=128, nullable=False, index=True)
    title: str = Field(sa_column=Column(Text, nullable=False))
    normalized_title: str = Field(max_length=510, nullable=False, index=True)
    sold_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    shipping_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    total_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    currency: str = Field(max_length=8, nullable=False, index=True)
    sold_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    condition: str | None = Field(default=None, max_length=255, nullable=True)
    listing_type: str | None = Field(default=None, max_length=64, nullable=True)
    item_url: str | None = Field(default=None, max_length=1024, nullable=True)
    image_url: str | None = Field(default=None, max_length=1024, nullable=True)
    raw_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    match_confidence: float = Field(default=0.0, nullable=False)
    imported_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class EbayCompImportRun(SQLModel, table=True):
    __tablename__ = "ebay_comp_import_run"
    __table_args__ = (
        SAIndex("ix_ebay_comp_import_owner_imported", "owner_user_id", "imported_at", "id"),
        SAIndex("ix_ebay_comp_import_owner_status_imported", "owner_user_id", "import_status", "imported_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    provider: str = Field(default="EBAY", max_length=32, nullable=False, index=True)
    import_status: str = Field(default="COMPLETED", max_length=24, nullable=False, index=True)
    search_criteria_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    fetched_count: int = Field(default=0, nullable=False)
    inserted_count: int = Field(default=0, nullable=False)
    updated_count: int = Field(default=0, nullable=False)
    duplicate_count: int = Field(default=0, nullable=False)
    error_count: int = Field(default=0, nullable=False)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    imported_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
