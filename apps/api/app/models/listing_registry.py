"""P36 canonical listing registry (truth layer; no marketplace automation)."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, Text, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Listing(SQLModel, table=True):
    __tablename__ = "listing"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_listing_owner_user_replay_key"),
        SAIndex("ix_listing_owner_user_id_status", "owner_user_id", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    canonical_comic_issue_id: int | None = Field(
        default=None,
        foreign_key="comic_issue.id",
        nullable=True,
        index=True,
    )
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)

    source_type: str = Field(max_length=40, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)

    title: str = Field(sa_column=Column(Text, nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    condition_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    asking_price_amount: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    asking_price_currency: str | None = Field(default=None, max_length=8, nullable=True)

    quantity: int = Field(default=1, nullable=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    activated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    sold_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    archived_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class ListingLifecycleEvent(SQLModel, table=True):
    """Append-only listing lifecycle spine."""

    __tablename__ = "listing_lifecycle_event"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "replay_key", name="uq_listing_lifecycle_event_listing_replay_key"
        ),
        SAIndex(
            "ix_listing_lifecycle_event_listing_id_created_at_id",
            "listing_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", nullable=False, index=True)

    event_type: str = Field(max_length=32, nullable=False, index=True)
    prior_status: str | None = Field(default=None, max_length=24, nullable=True)
    new_status: str | None = Field(default=None, max_length=24, nullable=True)

    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    created_by_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)

    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ListingPriceHistory(SQLModel, table=True):
    """Append-only listing price snapshots."""

    __tablename__ = "listing_price_history"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "replay_key", name="uq_listing_price_history_listing_replay_key"
        ),
        SAIndex(
            "ix_listing_price_history_listing_id_created_at_id", "listing_id", "created_at", "id"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", nullable=False, index=True)

    prior_amount: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    new_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(max_length=8, nullable=False)
    reason: str | None = Field(default=None, max_length=80, nullable=True)

    replay_key: str | None = Field(default=None, max_length=128, nullable=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ListingImage(SQLModel, table=True):
    """Gallery rows for listings (deterministic ordering by display_order, id)."""

    __tablename__ = "listing_image"
    __table_args__ = (
        UniqueConstraint("listing_id", "display_order", name="uq_listing_image_display_order"),
    )

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", nullable=False, index=True)

    cover_image_id: int | None = Field(
        default=None, foreign_key="cover_image.id", nullable=True, index=True
    )
    scan_session_item_id: int | None = Field(
        default=None,
        foreign_key="scan_session_item.id",
        nullable=True,
        index=True,
    )

    display_order: int = Field(default=0, nullable=False, index=True)
    role: str = Field(max_length=24, nullable=False, index=True)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ListingInventoryLink(SQLModel, table=True):
    """Allocated inventory linkage (future-ready; today one row per listing)."""

    __tablename__ = "listing_inventory_link"
    __table_args__ = (
        UniqueConstraint("listing_id", name="uq_listing_inventory_link_single_listing"),
    )

    id: int | None = Field(default=None, primary_key=True)

    listing_id: int = Field(foreign_key="listing.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    quantity_allocated: int = Field(default=1, nullable=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
