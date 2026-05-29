from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiveSaleSession(SQLModel, table=True):
    __tablename__ = "live_sale_sessions"
    __table_args__ = (
        SAIndex("ix_live_sale_session_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_live_sale_session_org_status_created", "organization_id", "session_status", "created_at", "id"),
        SAIndex(
            "ix_live_sale_session_account_created",
            "marketplace_account_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    session_name: str = Field(max_length=255, nullable=False)
    session_status: str = Field(max_length=24, nullable=False, index=True)
    planned_start_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    planned_end_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LiveSaleQueueItem(SQLModel, table=True):
    __tablename__ = "live_sale_queue_items"
    __table_args__ = (
        UniqueConstraint(
            "live_sale_session_id",
            "inventory_item_id",
            name="uq_live_sale_queue_inventory",
        ),
        SAIndex("ix_live_sale_queue_org_position", "organization_id", "queue_position", "id"),
        SAIndex("ix_live_sale_queue_session_position", "live_sale_session_id", "queue_position", "id"),
        SAIndex("ix_live_sale_queue_org_status_position", "organization_id", "item_status", "queue_position", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    live_sale_session_id: int = Field(foreign_key="live_sale_sessions.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(foreign_key="marketplace_listing_drafts.id", nullable=False, index=True)
    queue_position: int = Field(nullable=False, index=True)
    item_status: str = Field(max_length=24, nullable=False, index=True)
    planned_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_sale_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LiveSaleClaim(SQLModel, table=True):
    __tablename__ = "live_sale_claims"
    __table_args__ = (
        UniqueConstraint("live_sale_session_id", "live_sale_queue_item_id", "buyer_identifier", name="uq_live_sale_claim_identity"),
        SAIndex("ix_live_sale_claim_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_live_sale_claim_session_created", "live_sale_session_id", "created_at", "id"),
        SAIndex("ix_live_sale_claim_org_status_created", "organization_id", "claim_status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    live_sale_session_id: int = Field(foreign_key="live_sale_sessions.id", nullable=False, index=True)
    live_sale_queue_item_id: int = Field(foreign_key="live_sale_queue_items.id", nullable=False, index=True)
    buyer_identifier: str = Field(max_length=255, nullable=False, index=True)
    claim_status: str = Field(max_length=24, nullable=False, index=True)
    claimed_price: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    claimed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class LiveSaleEvent(SQLModel, table=True):
    __tablename__ = "live_sale_events"
    __table_args__ = (
        SAIndex("ix_live_sale_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_live_sale_event_session_created", "live_sale_session_id", "created_at", "id"),
        SAIndex("ix_live_sale_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_live_sale_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    live_sale_session_id: int | None = Field(default=None, foreign_key="live_sale_sessions.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
