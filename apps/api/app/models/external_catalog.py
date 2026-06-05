from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Index as SAIndex, Integer, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExternalCatalogSource(SQLModel, table=True):
    __tablename__ = "external_catalog_source"
    __table_args__ = (SAIndex("ix_external_catalog_source_name_active", "source_name", "is_active"),)

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(max_length=64, nullable=False, index=True)
    source_type: str = Field(max_length=32, nullable=False, index=True)
    base_url: str = Field(default="", sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ExternalCatalogIssue(SQLModel, table=True):
    __tablename__ = "external_catalog_issue"
    __table_args__ = (
        UniqueConstraint("source_name", "source_url", name="uq_external_catalog_issue_source_url"),
        SAIndex("ix_external_catalog_issue_source_release", "source_name", "release_date"),
        SAIndex("ix_external_catalog_issue_source_foc", "source_name", "foc_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(max_length=64, nullable=False, index=True)
    source_issue_id: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    source_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=160, nullable=False, index=True)
    series_name: str = Field(default="", max_length=200, nullable=False, index=True)
    issue_number: str | None = Field(default=None, max_length=24, nullable=True, index=True)
    issue_title: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    release_date: date | None = Field(default=None, nullable=True, index=True)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    cover_date: date | None = Field(default=None, nullable=True)
    price: float | None = Field(default=None, nullable=True)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    story_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    imprint: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    universe: str | None = Field(default=None, max_length=120, nullable=True, index=True)
    is_first_issue: bool = Field(default=False, nullable=False, index=True)
    is_milestone_issue: bool = Field(default=False, nullable=False, index=True)
    milestone_issue_number: int | None = Field(default=None, nullable=True, index=True)
    importance_signals_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    decision_signals_json: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="RDE-oriented signal bundle built at ingest (preview; no ranking change).",
    )
    pull_count: int | None = Field(default=None, nullable=True, index=True)
    want_count: int | None = Field(default=None, nullable=True, index=True)
    variant_count: int | None = Field(default=None, nullable=True)
    cover_image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    thumbnail_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    high_resolution_image_url: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    product_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    normalized_title_key: str = Field(default="", max_length=320, nullable=False, index=True)
    sync_status: str = Field(default="SYNCED", max_length=32, nullable=False, index=True)
    discovered_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    last_seen_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ExternalCatalogVariant(SQLModel, table=True):
    __tablename__ = "external_catalog_variant"
    __table_args__ = (
        UniqueConstraint(
            "external_issue_id",
            "cover_label",
            "variant_name",
            name="uq_external_catalog_variant_identity",
        ),
        SAIndex("ix_external_catalog_variant_issue", "external_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    cover_label: str | None = Field(default=None, max_length=64, nullable=True)
    variant_name: str | None = Field(default=None, max_length=200, nullable=True)
    artist: str | None = Field(default=None, max_length=160, nullable=True)
    ratio_value: int | None = Field(default=None, nullable=True)
    price: float | None = Field(default=None, nullable=True)
    image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    variant_detail_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ExternalCatalogCharacter(SQLModel, table=True):
    __tablename__ = "external_catalog_character"
    __table_args__ = (
        UniqueConstraint(
            "external_issue_id",
            "character_name",
            "role",
            name="uq_external_catalog_character_identity",
        ),
        SAIndex("ix_external_catalog_character_issue", "external_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    character_name: str = Field(max_length=200, nullable=False)
    alias: str | None = Field(default=None, max_length=200, nullable=True)
    role: str | None = Field(default=None, max_length=64, nullable=True)
    universe: str | None = Field(default=None, max_length=120, nullable=True)
    source_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ExternalCatalogCreator(SQLModel, table=True):
    __tablename__ = "external_catalog_creator"
    __table_args__ = (
        UniqueConstraint(
            "external_issue_id",
            "creator_name",
            "role",
            name="uq_external_catalog_creator_identity",
        ),
        SAIndex("ix_external_catalog_creator_issue", "external_issue_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    creator_name: str = Field(max_length=200, nullable=False)
    role: str | None = Field(default=None, max_length=64, nullable=True)
    role_display: str | None = Field(default=None, max_length=120, nullable=True)
    source_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ExternalCatalogSyncRun(SQLModel, table=True):
    __tablename__ = "external_catalog_sync_run"
    __table_args__ = (SAIndex("ix_external_catalog_sync_run_source_status", "source_name", "status", "started_at"),)

    id: int | None = Field(default=None, primary_key=True)
    source_name: str = Field(max_length=64, nullable=False, index=True)
    sync_type: str = Field(max_length=24, nullable=False, index=True)
    start_date: date | None = Field(default=None, nullable=True)
    end_date: date | None = Field(default=None, nullable=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    pages_scanned: int = Field(default=0, nullable=False)
    issues_created: int = Field(default=0, nullable=False)
    issues_updated: int = Field(default=0, nullable=False)
    variants_created: int = Field(default=0, nullable=False)
    creators_created: int = Field(default=0, nullable=False)
    errors_count: int = Field(default=0, nullable=False)
    error_sample: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ExternalCatalogMatch(SQLModel, table=True):
    __tablename__ = "external_catalog_match"
    __table_args__ = (
        UniqueConstraint("external_issue_id", "owner_user_id", name="uq_external_catalog_match_issue_owner"),
    )

    id: int | None = Field(default=None, primary_key=True)
    external_issue_id: int = Field(foreign_key="external_catalog_issue.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True, index=True)
    match_status: str = Field(max_length=32, nullable=False, index=True)
    match_confidence: float = Field(default=0.0, nullable=False)
    match_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
