"""P98 Master Universe reference skeleton (not catalog, not inventory)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


UNIVERSE_ISSUE_STATUS_DISCOVERED = "DISCOVERED"
UNIVERSE_ISSUE_STATUS_CATALOGED = "CATALOGED"

UNIVERSE_VARIANT_STATUS_DISCOVERED = "DISCOVERED"
UNIVERSE_VARIANT_STATUS_CATALOGED = "CATALOGED"

UNIVERSE_VARIANT_TYPES = (
    "STANDARD",
    "UNKNOWN",
    "NEWSSTAND",
    "DIRECT",
    "COVER_A",
    "COVER_B",
    "RATIO",
    "FOIL",
    "SECOND_PRINT",
    "STORE_EXCLUSIVE",
)

DEFAULT_VARIANT_TYPE = "UNKNOWN"


class UniversePublisher(SQLModel, table=True):
    __tablename__ = "universe_publisher"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_universe_publisher_normalized_name"),
        SAIndex("ix_universe_publisher_comicvine_id", "comicvine_publisher_id"),
        SAIndex("ix_universe_publisher_normalized_name", "normalized_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    comicvine_publisher_id: int | None = Field(default=None, nullable=True, index=True)
    name: str = Field(max_length=255, nullable=False)
    normalized_name: str = Field(max_length=255, nullable=False)
    country: str | None = Field(default=None, max_length=64, nullable=True)
    active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class UniverseVolume(SQLModel, table=True):
    __tablename__ = "universe_volume"
    __table_args__ = (
        UniqueConstraint("comicvine_volume_id", name="uq_universe_volume_comicvine_volume_id"),
        SAIndex("ix_universe_volume_publisher_id", "publisher_id"),
        SAIndex("ix_universe_volume_normalized_name", "normalized_name"),
    )

    id: int | None = Field(default=None, primary_key=True)
    comicvine_volume_id: int = Field(nullable=False, index=True)
    publisher_id: int = Field(foreign_key="universe_publisher.id", nullable=False)
    name: str = Field(max_length=512, nullable=False)
    normalized_name: str = Field(max_length=512, nullable=False)
    start_year: int | None = Field(default=None, nullable=True)
    count_of_issues: int | None = Field(default=None, nullable=True)
    volume_status: str = Field(default="active", max_length=32, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class UniverseIssue(SQLModel, table=True):
    __tablename__ = "universe_issue"
    __table_args__ = (
        UniqueConstraint("volume_id", "normalized_issue_number", name="uq_universe_issue_volume_number"),
        SAIndex("ix_universe_issue_volume_id", "volume_id"),
        SAIndex("ix_universe_issue_number", "issue_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    comicvine_issue_id: int | None = Field(default=None, nullable=True, index=True)
    volume_id: int = Field(foreign_key="universe_volume.id", nullable=False)
    issue_number: str = Field(max_length=32, nullable=False)
    normalized_issue_number: str = Field(max_length=32, nullable=False)
    issue_title: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    cover_date: date | None = Field(default=None, nullable=True)
    status: str = Field(default=UNIVERSE_ISSUE_STATUS_DISCOVERED, max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class UniverseVariant(SQLModel, table=True):
    __tablename__ = "universe_variant"
    __table_args__ = (
        SAIndex("ix_universe_variant_issue_id", "issue_id"),
        UniqueConstraint(
            "issue_id",
            "variant_type",
            "variant_name",
            name="uq_universe_variant_issue_type_name",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    issue_id: int = Field(foreign_key="universe_issue.id", nullable=False)
    variant_type: str = Field(max_length=32, nullable=False, index=True)
    variant_name: str = Field(default="", max_length=200, nullable=False)
    comicvine_variant_id: int | None = Field(default=None, nullable=True)
    catalog_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    status: str = Field(default=UNIVERSE_VARIANT_STATUS_DISCOVERED, max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AcquisitionUniverseLink(SQLModel, table=True):
    """Links a tree placeholder to a master universe variant (additive; placeholder row unchanged)."""

    __tablename__ = "acquisition_universe_link"
    __table_args__ = (UniqueConstraint("placeholder_id", name="uq_acquisition_universe_link_placeholder"),)

    id: int | None = Field(default=None, primary_key=True)
    placeholder_id: int = Field(foreign_key="acquisition_placeholder_issue.id", nullable=False, index=True)
    universe_variant_id: int = Field(foreign_key="universe_variant.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
