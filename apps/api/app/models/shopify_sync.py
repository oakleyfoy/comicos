from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShopifyStorefront(SQLModel, table=True):
    __tablename__ = "shopify_storefronts"
    __table_args__ = (
        UniqueConstraint("organization_id", "marketplace_account_id", name="uq_shopify_storefront_account"),
        UniqueConstraint("organization_id", "storefront_identifier", name="uq_shopify_storefront_identifier"),
        SAIndex("ix_shopify_storefront_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_shopify_storefront_org_status_created", "organization_id", "storefront_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    storefront_name: str = Field(max_length=255, nullable=False)
    storefront_status: str = Field(max_length=32, nullable=False, index=True)
    storefront_identifier: str = Field(max_length=255, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ShopifyProductMapping(SQLModel, table=True):
    __tablename__ = "shopify_product_mappings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "inventory_item_id",
            "marketplace_listing_draft_id",
            name="uq_shopify_product_mapping_identity",
        ),
        UniqueConstraint("organization_id", "storefront_product_identifier", name="uq_shopify_product_mapping_identifier"),
        SAIndex("ix_shopify_product_mapping_org_updated", "organization_id", "updated_at", "id"),
        SAIndex("ix_shopify_product_mapping_org_status_updated", "organization_id", "mapping_status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(foreign_key="marketplace_listing_drafts.id", nullable=False, index=True)
    storefront_product_identifier: str = Field(max_length=255, nullable=False, index=True)
    mapping_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ShopifySyncState(SQLModel, table=True):
    __tablename__ = "shopify_sync_states"
    __table_args__ = (
        UniqueConstraint("storefront_id", name="uq_shopify_sync_state_storefront"),
        SAIndex("ix_shopify_sync_state_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_shopify_sync_state_storefront_last_sync", "storefront_id", "last_sync_at", "id"),
        SAIndex("ix_shopify_sync_state_org_status_created", "organization_id", "sync_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    storefront_id: int = Field(foreign_key="shopify_storefronts.id", nullable=False, index=True)
    sync_status: str = Field(max_length=24, nullable=False, index=True)
    sync_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_sync_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ShopifySyncEvent(SQLModel, table=True):
    __tablename__ = "shopify_sync_events"
    __table_args__ = (
        SAIndex("ix_shopify_sync_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_shopify_sync_event_storefront_created", "storefront_id", "created_at", "id"),
        SAIndex("ix_shopify_sync_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_shopify_sync_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    storefront_id: int | None = Field(default=None, foreign_key="shopify_storefronts.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
