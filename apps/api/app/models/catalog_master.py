from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CatalogPublisher(SQLModel, table=True):
    __tablename__ = "catalog_publisher"
    __table_args__ = (SAIndex("ix_catalog_publisher_normalized_name", "normalized_name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False)
    aliases: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogSeries(SQLModel, table=True):
    __tablename__ = "catalog_series"
    __table_args__ = (
        SAIndex("ix_catalog_series_normalized_name", "normalized_name"),
        SAIndex("ix_catalog_series_publisher_id", "publisher_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    publisher_id: int | None = Field(default=None, foreign_key="catalog_publisher.id", nullable=True)
    name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False)
    volume_number: int | None = Field(default=None, nullable=True)
    start_year: int | None = Field(default=None, nullable=True)
    end_year: int | None = Field(default=None, nullable=True)
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    aliases: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogIssue(SQLModel, table=True):
    __tablename__ = "catalog_issue"
    __table_args__ = (
        SAIndex("ix_catalog_issue_series_number", "series_id", "normalized_issue_number"),
        SAIndex("ix_catalog_issue_publisher_id", "publisher_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    series_id: int = Field(foreign_key="catalog_series.id", nullable=False, index=True)
    publisher_id: int | None = Field(default=None, foreign_key="catalog_publisher.id", nullable=True)
    issue_number: str = Field(max_length=32, nullable=False, index=True)
    normalized_issue_number: str = Field(max_length=32, nullable=False)
    title: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    cover_date: date | None = Field(default=None, nullable=True)
    store_date: date | None = Field(default=None, nullable=True)
    release_date: date | None = Field(default=None, nullable=True, index=True)
    page_count: int | None = Field(default=None, nullable=True)
    cover_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source_confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogVariant(SQLModel, table=True):
    __tablename__ = "catalog_variant"
    __table_args__ = (SAIndex("ix_catalog_variant_issue_id", "issue_id"),)

    id: int | None = Field(default=None, primary_key=True)
    issue_id: int = Field(foreign_key="catalog_issue.id", nullable=False)
    variant_name: str | None = Field(default=None, max_length=200, nullable=True)
    cover_artist: str | None = Field(default=None, max_length=160, nullable=True)
    ratio: str | None = Field(default=None, max_length=32, nullable=True)
    print_run: int | None = Field(default=None, nullable=True)
    printing: str | None = Field(default=None, max_length=64, nullable=True)
    format: str | None = Field(default=None, max_length=64, nullable=True)
    sku: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogUpc(SQLModel, table=True):
    __tablename__ = "catalog_upc"
    __table_args__ = (UniqueConstraint("normalized_upc", name="uq_catalog_upc_normalized_upc"),)

    id: int | None = Field(default=None, primary_key=True)
    issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True, index=True)
    upc: str = Field(max_length=32, nullable=False, index=True)
    normalized_upc: str = Field(max_length=32, nullable=False, index=True)
    barcode_type: str | None = Field(default=None, max_length=32, nullable=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    confidence: Decimal = Field(default=Decimal("1.0"), sa_column=Column(Numeric(5, 2), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogImage(SQLModel, table=True):
    __tablename__ = "catalog_image"
    __table_args__ = (SAIndex("ix_catalog_image_issue_id", "issue_id"),)

    id: int | None = Field(default=None, primary_key=True)
    issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True, index=True)
    source_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    local_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    image_type: str = Field(default="cover", max_length=32, nullable=False, index=True)
    width: int | None = Field(default=None, nullable=True)
    height: int | None = Field(default=None, nullable=True)
    checksum: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    source: str = Field(max_length=64, nullable=False, index=True)
    external_image_id: str | None = Field(default=None, max_length=128, nullable=True)
    download_status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    download_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    downloaded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    content_type: str | None = Field(default=None, max_length=128, nullable=True)
    file_size_bytes: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogImageFingerprint(SQLModel, table=True):
    __tablename__ = "catalog_image_fingerprint"
    __table_args__ = (UniqueConstraint("image_id", name="uq_catalog_image_fingerprint_image_id"),)

    id: int | None = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="catalog_image.id", nullable=False, index=True)
    issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True, index=True)
    phash: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    dhash: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    ahash: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    colorhash: str | None = Field(default=None, max_length=64, nullable=True)
    embedding: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogOcrMetadata(SQLModel, table=True):
    __tablename__ = "catalog_ocr_metadata"
    __table_args__ = (SAIndex("ix_catalog_ocr_metadata_image_id", "image_id"),)

    id: int | None = Field(default=None, primary_key=True)
    image_id: int | None = Field(default=None, foreign_key="catalog_image.id", nullable=True)
    issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True, index=True)
    ocr_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    extracted_series: str | None = Field(default=None, max_length=255, nullable=True)
    extracted_issue_number: str | None = Field(default=None, max_length=32, nullable=True)
    extracted_publisher: str | None = Field(default=None, max_length=255, nullable=True)
    extracted_price: str | None = Field(default=None, max_length=32, nullable=True)
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogCreator(SQLModel, table=True):
    __tablename__ = "catalog_creator"
    __table_args__ = (SAIndex("ix_catalog_creator_normalized_name", "normalized_name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False)
    aliases: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogCharacter(SQLModel, table=True):
    __tablename__ = "catalog_character"
    __table_args__ = (SAIndex("ix_catalog_character_normalized_name", "normalized_name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False)
    aliases: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogStoryArc(SQLModel, table=True):
    __tablename__ = "catalog_story_arc"
    __table_args__ = (SAIndex("ix_catalog_story_arc_normalized_name", "normalized_name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False, index=True)
    normalized_name: str = Field(max_length=255, nullable=False)
    external_source_ids: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogRelationship(SQLModel, table=True):
    __tablename__ = "catalog_relationship"
    __table_args__ = (
        SAIndex(
            "ix_catalog_relationship_source",
            "source_type",
            "source_id",
            "relationship_type",
        ),
        SAIndex("ix_catalog_relationship_target", "target_type", "target_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_type: str = Field(max_length=64, nullable=False, index=True)
    source_id: int = Field(nullable=False, index=True)
    target_type: str = Field(max_length=64, nullable=False, index=True)
    target_id: int = Field(nullable=False, index=True)
    relationship_type: str = Field(max_length=64, nullable=False, index=True)
    role: str | None = Field(default=None, max_length=64, nullable=True)
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 2), nullable=True))
    source: str | None = Field(default=None, max_length=64, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CatalogMatchFeedback(SQLModel, table=True):
    __tablename__ = "catalog_match_feedback"
    __table_args__ = (SAIndex("ix_catalog_match_feedback_scan_session", "scan_session_id"),)

    id: int | None = Field(default=None, primary_key=True)
    scan_session_id: int | None = Field(default=None, foreign_key="inventory_scan_session.id", nullable=True)
    scan_item_id: int | None = Field(default=None, foreign_key="inventory_scan_item.id", nullable=True, index=True)
    submitted_image_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    submitted_upc: str | None = Field(default=None, max_length=32, nullable=True)
    predicted_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    predicted_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    correct_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True)
    correct_variant_id: int | None = Field(default=None, foreign_key="catalog_variant.id", nullable=True)
    confidence_before: Decimal | None = Field(default=None, sa_column=Column(Numeric(5, 2), nullable=True))
    feedback_type: str = Field(max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
