from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


MARKETPLACE_ACQUISITION_SOURCE_TYPES = (
    "EBAY",
    "WHATNOT",
    "MYCOMICSHOP",
    "COMICLINK",
    "COMICCONNECT",
    "MANUAL",
    "OTHER",
)

CANDIDATE_RECOMMENDATIONS = ("BUY", "WATCH", "PASS")
CANDIDATE_STATUSES = ("NEW", "REVIEWED", "IGNORED", "ACQUIRED")

DEFAULT_CANDIDATE_STATUS = "NEW"
DEFAULT_RECOMMENDATION = "WATCH"


class MarketplaceSource(SQLModel, table=True):
    __tablename__ = "marketplace_source"
    __table_args__ = (SAIndex("ix_marketplace_source_type_active", "source_type", "is_active", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=120, nullable=False)
    source_type: str = Field(max_length=32, nullable=False, index=True)
    base_url: str | None = Field(default=None, max_length=512, nullable=True)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceAcquisitionCandidate(SQLModel, table=True):
    __tablename__ = "marketplace_acquisition_candidate"
    __table_args__ = (
        SAIndex("ix_mac_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_mac_owner_rec", "owner_user_id", "recommendation", "id"),
        SAIndex("ix_mac_owner_source", "owner_user_id", "marketplace_source_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    marketplace_source_id: int | None = Field(default=None, foreign_key="marketplace_source.id", nullable=True, index=True)
    acquisition_opportunity_id: int | None = Field(
        default=None,
        foreign_key="acquisition_opportunity.id",
        nullable=True,
        index=True,
    )
    title: str = Field(max_length=300, nullable=False)
    publisher: str | None = Field(default=None, max_length=120, nullable=True)
    series_name: str | None = Field(default=None, max_length=200, nullable=True)
    issue_number: str | None = Field(default=None, max_length=32, nullable=True)
    variant_description: str | None = Field(default=None, max_length=200, nullable=True)
    listing_url: str | None = Field(default=None, max_length=1024, nullable=True)
    asking_price: float | None = Field(default=None, nullable=True)
    shipping_price: float | None = Field(default=None, nullable=True)
    total_price: float | None = Field(default=None, nullable=True)
    condition_description: str | None = Field(default=None, max_length=200, nullable=True)
    grade_label: str | None = Field(default=None, max_length=64, nullable=True)
    seller_name: str | None = Field(default=None, max_length=200, nullable=True)
    match_confidence: float = Field(default=0.0, nullable=False)
    value_score: float = Field(default=0.0, nullable=False)
    recommendation: str = Field(default=DEFAULT_RECOMMENDATION, max_length=16, nullable=False, index=True)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    status: str = Field(default=DEFAULT_CANDIDATE_STATUS, max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
