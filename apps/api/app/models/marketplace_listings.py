from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, String
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceListingDraft(SQLModel, table=True):
    __tablename__ = "marketplace_listing_drafts"
    __table_args__ = (
        SAIndex(
            "ix_mkt_listing_draft_org_status_created",
            "organization_id",
            "listing_status",
            "created_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_listing_draft_org_account_created",
            "organization_id",
            "marketplace_account_id",
            "created_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_listing_draft_org_inventory_created",
            "organization_id",
            "inventory_item_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    listing_title: str = Field(max_length=500, nullable=False)
    listing_description: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    listing_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    listing_currency: str = Field(default="USD", max_length=8, nullable=False)
    listing_quantity: int = Field(default=1, nullable=False)
    listing_status: str = Field(max_length=24, nullable=False, index=True)
    validation_status: str = Field(max_length=24, nullable=False, index=True)
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceListingProjection(SQLModel, table=True):
    __tablename__ = "marketplace_listing_projections"
    __table_args__ = (
        SAIndex(
            "ix_mkt_listing_proj_draft_generated",
            "marketplace_listing_draft_id",
            "generated_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_listing_proj_org_type_generated",
            "organization_id",
            "marketplace_type",
            "generated_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(foreign_key="marketplace_listing_drafts.id", nullable=False, index=True)
    marketplace_type: str = Field(max_length=32, nullable=False, index=True)
    projection_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    projection_status: str = Field(max_length=24, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceListingEvent(SQLModel, table=True):
    __tablename__ = "marketplace_listing_events"
    __table_args__ = (
        SAIndex("ix_mkt_listing_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mkt_listing_event_draft_created", "marketplace_listing_draft_id", "created_at", "id"),
        SAIndex("ix_mkt_listing_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_mkt_listing_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_listing_draft_id: int | None = Field(
        default=None,
        foreign_key="marketplace_listing_drafts.id",
        nullable=True,
        index=True,
    )
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
