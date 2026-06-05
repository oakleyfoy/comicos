"""P68 Real FMV / Market Pricing Engine models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel

P68_SOURCE_VERSION = "P68-01-06"

PROVIDER_MANUAL = "MANUAL"
PROVIDER_EBAY_SOLD = "EBAY_SOLD"
PROVIDER_GOCOLLECT = "GOCOLLECT"
PROVIDER_COVRPRICE = "COVRPRICE"
PROVIDER_HERITAGE = "HERITAGE"
PROVIDER_COMIC_PRICE_GUIDE = "COMIC_PRICE_GUIDE"
PROVIDER_INTERNAL_SALE = "INTERNAL_SALE"
PROVIDER_STUB = "STUB"

PROVIDER_TYPES = (
    PROVIDER_MANUAL,
    PROVIDER_EBAY_SOLD,
    PROVIDER_GOCOLLECT,
    PROVIDER_COVRPRICE,
    PROVIDER_HERITAGE,
    PROVIDER_COMIC_PRICE_GUIDE,
    PROVIDER_INTERNAL_SALE,
    PROVIDER_STUB,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P68MarketPricingProvider(SQLModel, table=True):
    __tablename__ = "p68_market_pricing_provider"
    __table_args__ = (SAIndex("ix_p68_mkt_provider_owner", "owner_user_id", "provider_type", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    provider_type: str = Field(max_length=32, nullable=False, index=True)
    enabled: bool = Field(default=True, nullable=False)
    health_status: str = Field(default="OK", max_length=16, nullable=False)
    last_ingest_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P68MarketPriceObservation(SQLModel, table=True):
    __tablename__ = "p68_market_price_observation"
    __table_args__ = (SAIndex("ix_p68_mkt_obs_owner_obs", "owner_user_id", "observed_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    provider: str = Field(max_length=32, nullable=False, index=True)
    source_url: str | None = Field(default=None, max_length=1024, nullable=True)
    external_listing_id: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    observed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    sale_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    series_key: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    variant_label: str | None = Field(default=None, max_length=255, nullable=True)
    printing_number: int | None = Field(default=None, nullable=True)
    printing_kind: str | None = Field(default=None, max_length=32, nullable=True)
    grade: str | None = Field(default=None, max_length=32, nullable=True)
    raw_or_graded: str = Field(default="raw", max_length=16, nullable=False, index=True)
    sold_price: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    shipping_price: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    total_price: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(default="USD", max_length=8, nullable=False)
    condition_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    confidence: float = Field(default=0.5, nullable=False)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class P68MarketPriceSnapshot(SQLModel, table=True):
    __tablename__ = "p68_market_price_snapshot"
    __table_args__ = (SAIndex("ix_p68_mkt_snap_owner_gen", "owner_user_id", "generated_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    variant_label: str | None = Field(default=None, max_length=255, nullable=True)
    printing_number: int | None = Field(default=None, nullable=True)
    printing_kind: str | None = Field(default=None, max_length=32, nullable=True)
    raw_fmv: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    graded_fmv: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    blended_fmv: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    low_sale: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    high_sale: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    median_sale: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    average_sale: float | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    sales_count: int = Field(default=0, nullable=False)
    liquidity_score: float = Field(default=0.0, nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    price_trend_30d: str = Field(default="STABLE", max_length=16, nullable=False)
    price_trend_90d: str = Field(default="STABLE", max_length=16, nullable=False)
    primary_provider: str = Field(default="", max_length=32, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source_version: str = Field(default=P68_SOURCE_VERSION, max_length=16, nullable=False)


class P68MarketPriceMatchResult(SQLModel, table=True):
    __tablename__ = "p68_market_price_match_result"
    __table_args__ = (SAIndex("ix_p68_mkt_match_obs", "observation_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    observation_id: int = Field(foreign_key="p68_market_price_observation.id", nullable=False, index=True)
    target_inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    match_score: float = Field(default=0.0, nullable=False)
    matched: bool = Field(default=False, nullable=False, index=True)
    matched_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    rejected_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    identity_warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class P68InventoryComputedFmv(SQLModel, table=True):
    __tablename__ = "p68_inventory_computed_fmv"
    __table_args__ = (SAIndex("ix_p68_inv_computed_fmv_owner", "owner_user_id", "inventory_copy_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    snapshot_id: int | None = Field(default=None, foreign_key="p68_market_price_snapshot.id", nullable=True)
    computed_fmv: float = Field(default=0.0, sa_column=Column(Numeric(12, 2), nullable=False))
    computed_fmv_source: str = Field(default="", max_length=64, nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    provider_blend_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
