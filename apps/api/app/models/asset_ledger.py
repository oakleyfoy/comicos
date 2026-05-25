from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Publisher(SQLModel, table=True):
    __tablename__ = "publisher"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MetadataAlias(SQLModel, table=True):
    __tablename__ = "metadata_alias"
    __table_args__ = (
        UniqueConstraint("alias_type", "alias_value", name="uq_metadata_alias_alias_type_value"),
    )

    id: int | None = Field(default=None, primary_key=True)
    alias_value: str = Field(max_length=255, nullable=False)
    canonical_value: str = Field(max_length=255, nullable=False)
    alias_type: str = Field(default="publisher", max_length=50, nullable=False, index=True)
    source: str = Field(default="manual", max_length=50, nullable=False)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MetadataAudit(SQLModel, table=True):
    __tablename__ = "metadata_audit"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(max_length=50, nullable=False, index=True)
    entity_id: int = Field(nullable=False, index=True)
    action: str = Field(max_length=50, nullable=False, index=True)
    before_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CanonicalSeries(SQLModel, table=True):
    __tablename__ = "canonical_series"
    __table_args__ = (UniqueConstraint("series_key", name="uq_canonical_series_series_key"),)

    id: int | None = Field(default=None, primary_key=True)
    canonical_title: str = Field(max_length=255, nullable=False, index=True)
    canonical_publisher: str = Field(max_length=255, nullable=False, index=True)
    series_key: str = Field(max_length=1024, nullable=False)
    first_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    earliest_known_release_date: date | None = Field(default=None, nullable=True)
    latest_known_release_date: date | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))


class CanonicalCreator(SQLModel, table=True):
    __tablename__ = "canonical_creator"
    __table_args__ = (UniqueConstraint("creator_key", name="uq_canonical_creator_creator_key"),)

    id: int | None = Field(default=None, primary_key=True)
    canonical_name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False, index=True)
    creator_key: str = Field(max_length=1024, nullable=False)
    first_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))


class ComicTitle(SQLModel, table=True):
    __tablename__ = "comic_title"

    id: int | None = Field(default=None, primary_key=True)
    publisher_id: int = Field(foreign_key="publisher.id", nullable=False, index=True)
    name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ComicIssue(SQLModel, table=True):
    __tablename__ = "comic_issue"

    id: int | None = Field(default=None, primary_key=True)
    comic_title_id: int = Field(foreign_key="comic_title.id", nullable=False, index=True)
    issue_number: str = Field(max_length=50, nullable=False)
    cover_date: date | None = Field(default=None, nullable=True)
    release_date: date | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Variant(SQLModel, table=True):
    __tablename__ = "variant"

    id: int | None = Field(default=None, primary_key=True)
    comic_issue_id: int = Field(foreign_key="comic_issue.id", nullable=False, index=True)
    cover_name: str | None = Field(default=None, max_length=255)
    printing: str | None = Field(default=None, max_length=100)
    ratio: str | None = Field(default=None, max_length=100)
    variant_type: str | None = Field(default=None, max_length=100)
    cover_artist: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Order(SQLModel, table=True):
    __tablename__ = "customer_order"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    retailer: str = Field(max_length=255, nullable=False)
    order_date: date = Field(nullable=False)
    source_type: str | None = Field(default=None, max_length=100)
    shipping_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    total_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="customer_order.id", nullable=False, index=True)
    variant_id: int = Field(foreign_key="variant.id", nullable=False, index=True)
    quantity: int = Field(nullable=False)
    raw_item_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    allocated_shipping: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    allocated_tax: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    all_in_unit_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryCopy(SQLModel, table=True):
    __tablename__ = "inventory_copy"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    order_item_id: int = Field(foreign_key="order_item.id", nullable=False, index=True)
    variant_id: int = Field(foreign_key="variant.id", nullable=False, index=True)
    copy_number: int = Field(nullable=False)
    acquisition_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    metadata_identity_key: str | None = Field(
        default=None,
        sa_column=Column(String(length=1024), nullable=True),
    )
    canonical_series_id: int | None = Field(
        default=None,
        foreign_key="canonical_series.id",
        index=True,
    )
    release_date: date | None = Field(default=None, nullable=True)
    release_year: int | None = Field(default=None, nullable=True)
    release_status: str = Field(default="unknown", max_length=30, nullable=False, index=True)
    order_status: str = Field(default="ordered", max_length=20, nullable=False, index=True)
    expected_ship_date: date | None = Field(default=None, nullable=True)
    received_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    condition_notes: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    grade_status: str = Field(default="raw", max_length=50, nullable=False)
    hold_status: str = Field(default="hold", max_length=50, nullable=False)
    current_fmv: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    star_rating: int | None = Field(default=None, nullable=True)
    primary_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryFmvSnapshot(SQLModel, table=True):
    __tablename__ = "inventory_fmv_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    inventory_copy_id: int = Field(
        foreign_key="inventory_copy.id",
        nullable=False,
        index=True,
    )
    previous_fmv: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    new_fmv: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    changed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    source: str = Field(default="manual", max_length=50, nullable=False)


class MarketSource(SQLModel, table=True):
    """Deterministic market-source registry row."""

    __tablename__ = "market_source"
    __table_args__ = (UniqueConstraint("source_name", name="uq_market_source_source_name"),)

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(max_length=120, nullable=False, index=True)
    source_type: str = Field(max_length=40, nullable=False, index=True)
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    import_priority: int = Field(default=0, nullable=False, index=True)
    supports_raw: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    supports_graded: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    supports_variants: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSourceSnapshot(SQLModel, table=True):
    """Append-only snapshot metadata for a market-source import pass."""

    __tablename__ = "market_source_snapshot"
    __table_args__ = (
        UniqueConstraint("market_source_id", "snapshot_date", name="uq_market_source_snapshot_source_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_source_id: int = Field(foreign_key="market_source.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    import_status: str = Field(max_length=32, nullable=False, index=True)
    total_records: int = Field(default=0, nullable=False)
    imported_records: int = Field(default=0, nullable=False)
    failed_records: int = Field(default=0, nullable=False)
    skipped_records: int = Field(default=0, nullable=False)
    source_metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSourceImportRun(SQLModel, table=True):
    """Append-only market-source import run ledger with explicit lifecycle state."""

    __tablename__ = "market_source_import_run"

    id: int | None = Field(default=None, primary_key=True)
    market_source_id: int = Field(foreign_key="market_source.id", nullable=False, index=True)
    created_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    total_records: int = Field(default=0, nullable=False)
    imported_records: int = Field(default=0, nullable=False)
    failed_records: int = Field(default=0, nullable=False)
    skipped_records: int = Field(default=0, nullable=False)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketSourceImportRunEvent(SQLModel, table=True):
    """Append-only lifecycle event log for market-source import runs."""

    __tablename__ = "market_source_import_run_event"

    id: int | None = Field(default=None, primary_key=True)
    import_run_id: int = Field(foreign_key="market_source_import_run.id", nullable=False, index=True)
    event_type: str = Field(max_length=24, nullable=False, index=True)
    previous_status: str | None = Field(default=None, max_length=32, nullable=True)
    new_status: str = Field(max_length=32, nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSaleRecord(SQLModel, table=True):
    """Normalized market-sales row with preserved raw source values."""

    __tablename__ = "market_sale_record"
    __table_args__ = (
        UniqueConstraint("market_source_id", "source_listing_id", name="uq_market_sale_record_source_listing"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_source_id: int = Field(foreign_key="market_source.id", nullable=False, index=True)
    source_listing_id: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    source_snapshot_id: int | None = Field(
        default=None,
        foreign_key="market_source_snapshot.id",
        nullable=True,
        index=True,
    )
    listing_type: str = Field(max_length=24, nullable=False, index=True)
    raw_title: str = Field(max_length=510, nullable=False, index=True)
    normalized_title: str | None = Field(default=None, max_length=510, nullable=True, index=True)
    raw_issue: str = Field(max_length=120, nullable=False, index=True)
    normalized_issue: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    raw_publisher: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    normalized_publisher: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    raw_variant: str | None = Field(default=None, max_length=255, nullable=True)
    normalized_variant: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    raw_grade: str | None = Field(default=None, max_length=120, nullable=True)
    normalized_grade: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    raw_cert_number: str | None = Field(default=None, max_length=120, nullable=True)
    normalized_cert_number: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    sale_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    shipping_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    total_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    currency_code: str = Field(max_length=8, nullable=False, index=True)
    sale_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    seller_name: str | None = Field(default=None, max_length=255, nullable=True)
    buyer_name: str | None = Field(default=None, max_length=255, nullable=True)
    is_graded: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    grading_company: str | None = Field(default=None, max_length=80, nullable=True, index=True)
    is_signed: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    source_url: str | None = Field(default=None, max_length=1024, nullable=True)
    source_metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    normalization_status: str = Field(max_length=32, nullable=False, index=True)
    review_status: str = Field(default="pending", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSaleRecordImage(SQLModel, table=True):
    """Ordered evidence/media attachment for a market sale record."""

    __tablename__ = "market_sale_record_image"
    __table_args__ = (
        UniqueConstraint("market_sale_record_id", "display_order", name="uq_market_sale_record_image_order"),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_sale_record_id: int = Field(foreign_key="market_sale_record.id", nullable=False, index=True)
    image_url: str | None = Field(default=None, max_length=1024, nullable=True)
    image_sha256: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    display_order: int = Field(nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSaleNormalizationIssue(SQLModel, table=True):
    """Deterministic issue ledger for a normalized market sale record."""

    __tablename__ = "market_sale_normalization_issue"

    id: int | None = Field(default=None, primary_key=True)
    market_sale_record_id: int = Field(foreign_key="market_sale_record.id", nullable=False, index=True)
    issue_type: str = Field(max_length=40, nullable=False, index=True)
    severity: str = Field(max_length=20, nullable=False, index=True)
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MarketSaleReviewAction(SQLModel, table=True):
    """Append-only human review audit trail for market-sale normalization workflows."""

    __tablename__ = "market_sale_review_action"

    id: int | None = Field(default=None, primary_key=True)
    market_sale_record_id: int = Field(foreign_key="market_sale_record.id", nullable=False, index=True)
    action_type: str = Field(max_length=40, nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    before_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    after_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImage(SQLModel, table=True):
    __tablename__ = "cover_image"

    id: int | None = Field(default=None, primary_key=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", index=True)
    canonical_series_id: int | None = Field(
        default=None,
        foreign_key="canonical_series.id",
        index=True,
    )
    draft_import_id: int | None = Field(default=None, foreign_key="draft_import.id", index=True)
    source_type: str = Field(max_length=50, nullable=False)
    original_filename: str | None = Field(default=None, max_length=510, nullable=True)
    storage_path: str = Field(max_length=512, nullable=False)
    mime_type: str = Field(max_length=255, nullable=False)
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    file_size: int | None = Field(default=None, nullable=True)
    sha256_hash: str = Field(max_length=64, nullable=False, index=True)
    processing_status: str = Field(default="pending", max_length=20, nullable=False, index=True)
    processing_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    processed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    metadata_refreshed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    matching_status: str = Field(default="not_ready", max_length=20, nullable=False, index=True)
    matching_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ready_for_matching_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageDerivative(SQLModel, table=True):
    __tablename__ = "cover_image_derivative"
    __table_args__ = (
        UniqueConstraint(
            "cover_image_id",
            "derivative_type",
            name="uq_cover_image_derivative_cover_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    derivative_type: str = Field(max_length=20, nullable=False, index=True)
    storage_path: str = Field(max_length=512, nullable=False)
    mime_type: str = Field(max_length=255, nullable=False)
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    file_size: int | None = Field(default=None, nullable=True)
    sha256_hash: str = Field(max_length=64, nullable=False, index=True)
    generated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageOcrRegion(SQLModel, table=True):
    __tablename__ = "cover_image_ocr_region"
    __table_args__ = (
        UniqueConstraint(
            "cover_image_id",
            "region_type",
            name="uq_cover_image_ocr_region_cover_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    derivative_id: int | None = Field(
        default=None,
        foreign_key="cover_image_derivative.id",
        nullable=True,
        index=True,
    )
    region_type: str = Field(max_length=50, nullable=False, index=True)
    storage_path: str = Field(max_length=512, nullable=False)
    mime_type: str = Field(max_length=255, nullable=False)
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    file_size: int | None = Field(default=None, nullable=True)
    sha256_hash: str = Field(max_length=64, nullable=False, index=True)
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageOcrResult(SQLModel, table=True):
    __tablename__ = "cover_image_ocr_result"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    source_cover_image_sha256: str | None = Field(default=None, max_length=64, nullable=True)
    source_thumb_derivative_sha256: str | None = Field(default=None, max_length=64, nullable=True)
    source_medium_derivative_sha256: str | None = Field(default=None, max_length=64, nullable=True)
    source_processing_version: str | None = Field(default=None, max_length=100, nullable=True)
    normalization_version: str | None = Field(default=None, max_length=100, nullable=True)
    replay_of_ocr_result_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_result.id",
        nullable=True,
        index=True,
    )
    replay_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ocr_engine: str = Field(max_length=50, nullable=False)
    ocr_engine_version: str | None = Field(default=None, max_length=255, nullable=True)
    processing_status: str = Field(default="pending", max_length=20, nullable=False, index=True)
    raw_text: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    normalized_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    confidence_score: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    processing_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    processed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    processing_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageOcrCandidate(SQLModel, table=True):
    __tablename__ = "cover_image_ocr_candidate"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    ocr_result_id: int = Field(foreign_key="cover_image_ocr_result.id", nullable=False, index=True)
    candidate_type: str = Field(max_length=50, nullable=False, index=True)
    raw_candidate_text: str = Field(sa_column=Column(Text, nullable=False))
    normalized_candidate_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    confidence_score: float | None = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
    )
    extraction_source: str = Field(max_length=50, nullable=False, index=True)
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    review_status: str = Field(default="pending", max_length=20, nullable=False, index=True)
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    reviewed_by_user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        index=True,
    )
    review_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageOcrReconciliationWarning(SQLModel, table=True):
    __tablename__ = "cover_image_ocr_reconciliation_warning"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(
        default=None,
        foreign_key="inventory_copy.id",
        nullable=True,
        index=True,
    )
    ocr_candidate_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_candidate.id",
        nullable=True,
        index=True,
    )
    warning_type: str = Field(max_length=50, nullable=False, index=True)
    severity: str = Field(max_length=20, nullable=False, index=True)
    current_metadata_value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    candidate_value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    message: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="open", max_length=20, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    resolved_by_user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        index=True,
    )


class CoverImageBarcodeCandidate(SQLModel, table=True):
    __tablename__ = "cover_image_barcode_candidate"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    source_ocr_result_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_result.id",
        nullable=True,
        index=True,
    )
    source_ocr_candidate_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_candidate.id",
        nullable=True,
        index=True,
    )
    raw_barcode_value: str = Field(sa_column=Column(Text, nullable=False))
    normalized_upc_value: str = Field(max_length=32, nullable=False, index=True)
    barcode_type: str = Field(default="unknown", max_length=20, nullable=False, index=True)
    confidence: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    review_state: str = Field(default="pending", max_length=20, nullable=False, index=True)
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    reviewed_by_user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageFingerprint(SQLModel, table=True):
    __tablename__ = "cover_image_fingerprint"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    fingerprint_type: str = Field(max_length=20, nullable=False, index=True)
    fingerprint_value: str = Field(max_length=255, nullable=False)
    derivative_type: str = Field(max_length=20, nullable=False, index=True)
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    image_sha256: str | None = Field(default=None, max_length=64, nullable=True)
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverImageOcrQualityAnalysis(SQLModel, table=True):
    __tablename__ = "cover_image_ocr_quality_analysis"
    __table_args__ = (
        UniqueConstraint(
            "cover_image_id",
            "quality_type",
            "extraction_version",
            name="uq_cover_image_ocr_quality_analysis_signature",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    source_ocr_result_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_result.id",
        nullable=True,
        index=True,
    )
    quality_type: str = Field(max_length=30, nullable=False, index=True)
    deterministic_score: float = Field(sa_column=Column(Float, nullable=False))
    severity: str = Field(max_length=20, nullable=False, index=True)
    detail_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OcrBatch(SQLModel, table=True):
    __tablename__ = "ocr_batch"

    id: int | None = Field(default=None, primary_key=True)
    batch_key: str = Field(max_length=120, nullable=False, index=True, unique=True)
    status: str = Field(max_length=30, nullable=False, index=True)
    total_items: int = Field(default=0, nullable=False)
    pending_count: int = Field(default=0, nullable=False)
    running_count: int = Field(default=0, nullable=False)
    completed_count: int = Field(default=0, nullable=False)
    failed_count: int = Field(default=0, nullable=False)
    skipped_count: int = Field(default=0, nullable=False)
    created_by: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    batch_options_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))


class OcrBatchItem(SQLModel, table=True):
    __tablename__ = "ocr_batch_item"
    __table_args__ = (
        UniqueConstraint("batch_id", "cover_image_id", name="uq_ocr_batch_item_batch_cover"),
    )

    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="ocr_batch.id", nullable=False, index=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    status: str = Field(max_length=20, nullable=False, index=True)
    job_id: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OcrReplayRun(SQLModel, table=True):
    __tablename__ = "ocr_replay_run"

    id: int | None = Field(default=None, primary_key=True)
    replay_type: str = Field(max_length=40, nullable=False, index=True)
    extraction_version_from: str = Field(max_length=255, nullable=False)
    extraction_version_to: str = Field(max_length=255, nullable=False)
    status: str = Field(max_length=30, nullable=False, index=True)
    total_items: int = Field(default=0, nullable=False)
    changed_items: int = Field(default=0, nullable=False)
    unchanged_items: int = Field(default=0, nullable=False)
    failed_items: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_by: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)


class OcrReplayItem(SQLModel, table=True):
    __tablename__ = "ocr_replay_item"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "cover_image_id", name="uq_ocr_replay_item_run_cover"),
    )

    id: int | None = Field(default=None, primary_key=True)
    replay_run_id: int = Field(foreign_key="ocr_replay_run.id", nullable=False, index=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    status: str = Field(max_length=20, nullable=False, index=True)
    previous_snapshot_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    replay_snapshot_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    diff_summary_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class CoverImageMatchCandidate(SQLModel, table=True):
    __tablename__ = "cover_image_match_candidate"
    __table_args__ = (
        UniqueConstraint(
            "source_cover_image_id",
            "candidate_cover_image_id",
            "candidate_type",
            "extraction_version",
            name="uq_cover_image_match_candidate_signature",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_cover_image_id: int = Field(
        foreign_key="cover_image.id",
        nullable=False,
        index=True,
    )
    candidate_cover_image_id: int = Field(
        foreign_key="cover_image.id",
        nullable=False,
        index=True,
    )
    candidate_type: str = Field(max_length=30, nullable=False, index=True)
    confidence_bucket: str = Field(max_length=20, nullable=False, index=True)
    deterministic_score: float = Field(sa_column=Column(Float, nullable=False))
    normalized_confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_version: str = Field(max_length=100, nullable=False, index=True, default="cover-match-confidence-v1")
    scoring_breakdown_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    matched_signal_count: int = Field(default=0, nullable=False)
    hard_match_flags_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    weak_signal_flags_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    ranking_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    ranking_version: str = Field(max_length=100, nullable=False, index=True, default="cover-match-ranking-v1")
    ranking_reason_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    candidate_rank: int = Field(default=0, nullable=False, index=True)
    grouping_key: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    grouping_type: str | None = Field(default=None, max_length=50, nullable=True, index=True)
    grouping_confidence_bucket: str | None = Field(default=None, max_length=20, nullable=True)
    grouping_reason_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    matched_signals: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    extraction_version: str = Field(max_length=100, nullable=False, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    dismissed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class CoverImageLinkDecision(SQLModel, table=True):
    __tablename__ = "cover_image_link_decision"

    id: int | None = Field(default=None, primary_key=True)
    source_cover_image_id: int = Field(
        foreign_key="cover_image.id",
        nullable=False,
        index=True,
    )
    candidate_cover_image_id: int = Field(
        foreign_key="cover_image.id",
        nullable=False,
        index=True,
    )
    pair_key: str = Field(max_length=255, nullable=False, index=True)
    source_match_candidate_id: int | None = Field(
        default=None,
        foreign_key="cover_image_match_candidate.id",
        nullable=True,
        index=True,
    )
    decision_type: str = Field(max_length=30, nullable=False, index=True)
    relationship_type: str = Field(max_length=30, nullable=False, index=True)
    decision_state: str = Field(max_length=20, nullable=False, index=True, default="active")
    reviewer_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    decision_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    decision_source: str = Field(max_length=20, nullable=False, index=True, default="human")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    reverted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    superseded_by_decision_id: int | None = Field(
        default=None,
        foreign_key="cover_image_link_decision.id",
        nullable=True,
        index=True,
    )


class DraftImport(SQLModel, table=True):
    __tablename__ = "draft_import"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    raw_text: str = Field(sa_column=Column(String, nullable=False))
    parsed_payload_json: dict = Field(sa_column=Column(JSON, nullable=False))
    confidence_score: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(4, 2), nullable=False, default=Decimal("0")),
    )
    status: str = Field(default="draft", max_length=20, nullable=False)
    linked_order_id: int | None = Field(default=None, foreign_key="customer_order.id", index=True)
    primary_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    password_hash: str = Field(max_length=255, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class DuplicateCandidateReview(SQLModel, table=True):
    __tablename__ = "duplicate_candidate_review"
    __table_args__ = (
        UniqueConstraint(
            "metadata_identity_key",
            name="uq_duplicate_candidate_review_metadata_key",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    metadata_identity_key: str = Field(max_length=1024, nullable=False)
    review_status: str = Field(max_length=40, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    reviewed_by_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CanonicalIssueLinkSuggestion(SQLModel, table=True):
    __tablename__ = "canonical_issue_link_suggestion"

    id: int | None = Field(default=None, primary_key=True)
    cover_image_id: int = Field(foreign_key="cover_image.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    canonical_series_id: int | None = Field(
        default=None,
        foreign_key="canonical_series.id",
        nullable=True,
        index=True,
    )
    canonical_publisher_id: int | None = Field(default=None, foreign_key="publisher.id", nullable=True, index=True)
    suggested_metadata_identity_key: str | None = Field(
        default=None,
        sa_column=Column(String(length=1024), nullable=True),
    )
    suggestion_type: str = Field(max_length=50, nullable=False, index=True)
    confidence_bucket: str = Field(max_length=20, nullable=False, index=True)
    deterministic_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    confidence_version: str = Field(
        max_length=100,
        nullable=False,
        index=True,
        default="canonical-issue-suggestion-v1",
    )
    evidence_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    suppression_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    review_state: str = Field(default="pending", max_length=20, nullable=False, index=True)
    reviewed_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CoverRelationshipConflict(SQLModel, table=True):
    __tablename__ = "cover_relationship_conflict"

    id: int | None = Field(default=None, primary_key=True)
    conflict_type: str = Field(max_length=80, nullable=False, index=True)
    severity: str = Field(max_length=20, nullable=False, index=True)
    source_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    related_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    link_decision_id: int | None = Field(
        default=None,
        foreign_key="cover_image_link_decision.id",
        nullable=True,
        index=True,
    )
    match_candidate_id: int | None = Field(
        default=None,
        foreign_key="cover_image_match_candidate.id",
        nullable=True,
        index=True,
    )
    canonical_issue_suggestion_id: int | None = Field(
        default=None,
        foreign_key="canonical_issue_link_suggestion.id",
        nullable=True,
        index=True,
    )
    conflict_key: str = Field(max_length=255, nullable=False, index=True, unique=True)
    status: str = Field(default="open", max_length=20, nullable=False, index=True)
    evidence_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    acknowledged_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    dismissed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class RelationshipReplayRun(SQLModel, table=True):
    __tablename__ = "relationship_replay_run"

    id: int | None = Field(default=None, primary_key=True)
    replay_type: str = Field(max_length=50, nullable=False, index=True)
    status: str = Field(max_length=30, nullable=False, index=True)
    total_items: int = Field(default=0, nullable=False)
    changed_items: int = Field(default=0, nullable=False)
    unchanged_items: int = Field(default=0, nullable=False)
    failed_items: int = Field(default=0, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_by: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    replay_version: str = Field(max_length=100, nullable=False, index=True)


class RelationshipReplayItem(SQLModel, table=True):
    __tablename__ = "relationship_replay_item"
    __table_args__ = (
        UniqueConstraint(
            "replay_run_id",
            "relationship_key",
            name="uq_relationship_replay_item_run_key",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    replay_run_id: int = Field(foreign_key="relationship_replay_run.id", nullable=False, index=True)
    cover_image_id: int | None = Field(default=None, foreign_key="cover_image.id", nullable=True, index=True)
    relationship_key: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    status: str = Field(max_length=20, nullable=False, index=True)
    previous_snapshot_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    replay_snapshot_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    diff_summary_json: dict = Field(sa_column=Column(JSON, nullable=False, default=dict))
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class GmailAccount(SQLModel, table=True):
    __tablename__ = "gmail_account"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True, unique=True)
    gmail_email: str = Field(max_length=320, nullable=False)
    google_subject_id: str = Field(max_length=255, nullable=False, unique=True, index=True)
    access_token_encrypted: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    refresh_token_encrypted: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    auto_sync_enabled: bool = Field(default=False, nullable=False)
    token_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_status: str | None = Field(default=None, max_length=50)
    last_sync_error: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class GmailImportRecord(SQLModel, table=True):
    __tablename__ = "gmail_import_record"

    id: int | None = Field(default=None, primary_key=True)
    gmail_account_id: int = Field(foreign_key="gmail_account.id", nullable=False, index=True)
    external_message_id: str = Field(max_length=255, nullable=False, unique=True, index=True)
    draft_import_id: int = Field(foreign_key="draft_import.id", nullable=False, index=True)
    imported_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OpsEvent(SQLModel, table=True):
    __tablename__ = "ops_event"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(max_length=100, nullable=False, index=True)
    status: str = Field(max_length=50, nullable=False, index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    job_id: str | None = Field(default=None, max_length=255, index=True)
    queue_name: str | None = Field(default=None, max_length=100)
    gmail_account_id: int | None = Field(default=None, foreign_key="gmail_account.id", index=True)
    draft_import_id: int | None = Field(default=None, foreign_key="draft_import.id", index=True)
    order_id: int | None = Field(default=None, foreign_key="customer_order.id", index=True)
    external_message_id: str | None = Field(default=None, max_length=255, index=True)
    message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ScannerProfile(SQLModel, table=True):
    """Scanner capture preset metadata — no runtime hardware integration."""

    __tablename__ = "scanner_profile"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    profile_name: str = Field(max_length=200, nullable=False)
    scanner_type: str = Field(max_length=40, nullable=False, index=True)
    dpi: int | None = Field(default=None, nullable=True)
    color_mode: str = Field(max_length=20, nullable=False)
    file_format: str = Field(max_length=10, nullable=False)
    duplex_enabled: bool = Field(default=False, nullable=False)
    feeder_enabled: bool = Field(default=False, nullable=False)
    recommended_use: str = Field(max_length=40, nullable=False, index=True)
    is_default: bool = Field(default=False, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ScanSession(SQLModel, table=True):
    __tablename__ = "scan_session"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    session_type: str = Field(max_length=40, nullable=False, index=True)
    status: str = Field(max_length=40, nullable=False, index=True)
    scanner_profile: str | None = Field(default=None, max_length=120, nullable=True)
    scanner_profile_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("scanner_profile.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    scanner_profile_snapshot: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    source_device: str | None = Field(default=None, max_length=120, nullable=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    total_items: int = Field(default=0, nullable=False)
    processed_items: int = Field(default=0, nullable=False)
    failed_items: int = Field(default=0, nullable=False)
    skipped_items: int = Field(default=0, nullable=False)
    session_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class ScanSessionItem(SQLModel, table=True):
    __tablename__ = "scan_session_item"
    __table_args__ = (
        UniqueConstraint("scan_session_id", "sequence_index", name="uq_scan_session_item_session_sequence_idx"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_session_id: int = Field(foreign_key="scan_session.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(
        default=None,
        foreign_key="inventory_copy.id",
        nullable=True,
        index=True,
    )
    cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    source_filename: str | None = Field(default=None, max_length=510, nullable=True)
    sequence_index: int = Field(nullable=False, index=True)
    ingest_status: str = Field(max_length=40, nullable=False, index=True)
    ingest_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    image_sha256: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ScanQaResult(SQLModel, table=True):
    """Deterministic scan QA verdict snapshot (written only via explicit run-qa; no pipelines)."""

    __tablename__ = "scan_qa_result"
    __table_args__ = (
        UniqueConstraint("scan_session_item_id", name="uq_scan_qa_result_session_item"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_session_id: int = Field(foreign_key="scan_session.id", nullable=False, index=True)
    scan_session_item_id: int = Field(foreign_key="scan_session_item.id", nullable=False, index=True)
    cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    qa_classification: str = Field(max_length=48, nullable=False, index=True)
    routing_recommendation: str = Field(max_length=48, nullable=False, index=True)
    severity: str = Field(max_length=20, nullable=False, index=True)
    evidence_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class QueueRoutingRecommendation(SQLModel, table=True):
    """Deterministic queue-routing snapshot (manual actions only)."""

    __tablename__ = "queue_routing_recommendation"
    __table_args__ = (
        UniqueConstraint("scan_session_item_id", name="uq_queue_routing_recommendation_session_item"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_session_item_id: int | None = Field(
        default=None,
        foreign_key="scan_session_item.id",
        nullable=True,
        index=True,
    )
    cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    recommendation_type: str = Field(max_length=48, nullable=False, index=True)
    priority: str = Field(max_length=16, nullable=False, index=True)
    routing_status: str = Field(default="open", max_length=20, nullable=False, index=True)
    evidence_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class HighResReviewRequest(SQLModel, table=True):
    """Deterministic Epson / flatbed high-resolution review workflow request (no auto-OCR enqueue)."""

    __tablename__ = "high_res_review_request"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)

    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)

    source_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )
    source_scan_session_item_id: int | None = Field(
        default=None,
        foreign_key="scan_session_item.id",
        nullable=True,
        index=True,
    )
    source_ocr_quality_analysis_id: int | None = Field(
        default=None,
        foreign_key="cover_image_ocr_quality_analysis.id",
        nullable=True,
        index=True,
    )
    source_inventory_risk_type: str | None = Field(default=None, max_length=80, nullable=True)
    source_action_center_category: str | None = Field(default=None, max_length=80, nullable=True)

    attach_scan_session_id: int | None = Field(
        default=None,
        foreign_key="scan_session.id",
        nullable=True,
        index=True,
    )
    attach_scan_session_item_id: int | None = Field(
        default=None,
        foreign_key="scan_session_item.id",
        nullable=True,
        index=True,
    )
    high_res_cover_image_id: int | None = Field(
        default=None,
        foreign_key="cover_image.id",
        nullable=True,
        index=True,
    )

    request_reason: str = Field(max_length=40, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    priority: str = Field(max_length=12, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanPipelineReplayRun(SQLModel, table=True):
    """Recorded scan-ingest pipeline replay/recovery tooling (comparison only — no mutations)."""

    __tablename__ = "scan_pipeline_replay_run"

    id: int | None = Field(default=None, primary_key=True)
    scan_session_id: int = Field(foreign_key="scan_session.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_version: str = Field(max_length=80, nullable=False, index=True)
    scopes_json: list[str] = Field(sa_column=Column(JSON, nullable=False))
    cancellation_requested: bool = Field(default=False, nullable=False, index=True)

    status: str = Field(max_length=28, nullable=False, index=True)
    total_items: int = Field(default=0, nullable=False)
    changed_items: int = Field(default=0, nullable=False)
    unchanged_items: int = Field(default=0, nullable=False)
    failed_items: int = Field(default=0, nullable=False)
    cancelled_items: int = Field(default=0, nullable=False)

    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ScanPipelineReplayItem(SQLModel, table=True):
    __tablename__ = "scan_pipeline_replay_item"
    __table_args__ = (
        UniqueConstraint("replay_run_id", "scan_session_item_id", name="uq_scan_pipeline_replay_item_run_item"),
    )

    id: int | None = Field(default=None, primary_key=True)
    replay_run_id: int = Field(foreign_key="scan_pipeline_replay_run.id", nullable=False, index=True)
    scan_session_item_id: int = Field(foreign_key="scan_session_item.id", nullable=False, index=True)

    result_state: str = Field(max_length=20, nullable=False, index=True)

    baseline_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    replay_snapshot_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    diff_categories_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    diff_summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
