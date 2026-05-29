from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplacePriceRecommendation(SQLModel, table=True):
    __tablename__ = "marketplace_price_recommendations"
    __table_args__ = (
        SAIndex("ix_mkt_pricing_rec_org_generated", "organization_id", "generated_at", "id"),
        SAIndex(
            "ix_mkt_pricing_rec_org_listing_generated",
            "organization_id",
            "marketplace_listing_draft_id",
            "generated_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_pricing_rec_org_status_generated",
            "organization_id",
            "recommendation_status",
            "generated_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_pricing_rec_org_account_generated",
            "organization_id",
            "marketplace_account_id",
            "generated_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(foreign_key="marketplace_listing_drafts.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    recommendation_type: str = Field(max_length=32, nullable=False, index=True)
    recommended_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    current_listing_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    floor_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    ceiling_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    recommendation_reason: str = Field(max_length=1000, nullable=False)
    recommendation_status: str = Field(max_length=24, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceOffer(SQLModel, table=True):
    __tablename__ = "marketplace_offers"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_account_id",
            "marketplace_offer_identifier",
            name="uq_marketplace_offer_identity",
        ),
        SAIndex("ix_mkt_offer_org_received", "organization_id", "received_at", "id"),
        SAIndex(
            "ix_mkt_offer_org_listing_received",
            "organization_id",
            "marketplace_listing_draft_id",
            "received_at",
            "id",
        ),
        SAIndex("ix_mkt_offer_org_status_received", "organization_id", "offer_status", "received_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(foreign_key="marketplace_listing_drafts.id", nullable=False, index=True)
    marketplace_offer_identifier: str = Field(max_length=255, nullable=False, index=True)
    offer_status: str = Field(max_length=24, nullable=False, index=True)
    offer_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    offer_currency: str = Field(max_length=8, nullable=False, index=True)
    buyer_identifier: str | None = Field(default=None, max_length=255, nullable=True, index=True)
    received_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplacePricingRule(SQLModel, table=True):
    __tablename__ = "marketplace_pricing_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "rule_key", name="uq_marketplace_pricing_rule_key"),
        SAIndex("ix_mkt_pricing_rule_org_updated", "organization_id", "updated_at", "id"),
        SAIndex("ix_mkt_pricing_rule_org_status_updated", "organization_id", "rule_status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    rule_key: str = Field(max_length=80, nullable=False, index=True)
    rule_name: str = Field(max_length=255, nullable=False)
    rule_status: str = Field(max_length=24, nullable=False, index=True)
    rule_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplacePricingEvent(SQLModel, table=True):
    __tablename__ = "marketplace_pricing_events"
    __table_args__ = (
        SAIndex("ix_mkt_pricing_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_mkt_pricing_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_mkt_pricing_event_account_created", "marketplace_account_id", "created_at", "id"),
        SAIndex(
            "ix_mkt_pricing_event_listing_created",
            "marketplace_listing_draft_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_mkt_pricing_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_accounts.id", nullable=True, index=True)
    marketplace_listing_draft_id: int | None = Field(default=None, foreign_key="marketplace_listing_drafts.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
