"""P88 marketplace opportunity source tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceOpportunitySource(SQLModel, table=True):
    __tablename__ = "p88_marketplace_opportunity_source"
    __table_args__ = (
        SAIndex("ix_p88_mkt_src_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_p88_mkt_src_opportunity", "opportunity_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    opportunity_id: int | None = Field(
        default=None,
        foreign_key="p82_marketplace_acquisition_opportunity.id",
        nullable=True,
        index=True,
    )
    marketplace: str = Field(default="OTHER", max_length=32, nullable=False, index=True)
    source_type: str = Field(default="MANUAL_IMPORT", max_length=32, nullable=False, index=True)
    source_url: str = Field(default="", max_length=2048, nullable=False)
    external_listing_id: str = Field(default="", max_length=128, nullable=False)
    source_status: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    notes: str = Field(default="", max_length=512, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
