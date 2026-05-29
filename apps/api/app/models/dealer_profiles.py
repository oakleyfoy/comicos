from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DealerProfile(SQLModel, table=True):
    __tablename__ = "dealer_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_dealer_profile_organization"),
        UniqueConstraint("public_slug", name="uq_dealer_profile_public_slug"),
        SAIndex("ix_dealer_profile_status_updated", "profile_status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    public_slug: str = Field(max_length=120, nullable=False, index=True)
    display_name: str = Field(max_length=200, nullable=False)
    tagline: str | None = Field(default=None, max_length=240, nullable=True)
    description: str | None = Field(default=None, nullable=True)
    logo_asset_id: int | None = Field(default=None, nullable=True, index=True)
    banner_asset_id: int | None = Field(default=None, nullable=True, index=True)
    website_url: str | None = Field(default=None, max_length=512, nullable=True)
    instagram_url: str | None = Field(default=None, max_length=512, nullable=True)
    whatnot_url: str | None = Field(default=None, max_length=512, nullable=True)
    location_label: str | None = Field(default=None, max_length=160, nullable=True)
    profile_status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerStorefrontSettings(SQLModel, table=True):
    __tablename__ = "dealer_storefront_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_dealer_storefront_settings_org"),)

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    storefront_visibility: str = Field(max_length=24, nullable=False, index=True)
    public_inventory_enabled: bool = Field(default=False, nullable=False)
    featured_inventory_limit: int = Field(default=12, nullable=False)
    featured_inventory_sort: str = Field(max_length=32, nullable=False, index=True)
    featured_manual_inventory_ids_json: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerStorefrontEvent(SQLModel, table=True):
    __tablename__ = "dealer_storefront_events"
    __table_args__ = (
        SAIndex("ix_dealer_storefront_event_org_created", "organization_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=64, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
