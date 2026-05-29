from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceInventoryState(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_states"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_account_id",
            "marketplace_listing_draft_id",
            name="uq_marketplace_inventory_state_account_draft",
        ),
        SAIndex(
            "ix_mkt_inventory_state_org_status_created",
            "organization_id",
            "sync_status",
            "created_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_inventory_state_org_account_created",
            "organization_id",
            "marketplace_account_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    marketplace_listing_draft_id: int = Field(
        foreign_key="marketplace_listing_drafts.id",
        nullable=False,
        index=True,
    )
    marketplace_listing_identifier: str = Field(max_length=255, nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    local_quantity: int = Field(nullable=False)
    marketplace_quantity: int = Field(nullable=False)
    sync_status: str = Field(max_length=24, nullable=False, index=True)
    last_sync_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceInventorySyncRun(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_sync_runs"
    __table_args__ = (
        SAIndex("ix_mkt_inventory_sync_run_org_started", "organization_id", "started_at", "id"),
        SAIndex(
            "ix_mkt_inventory_sync_run_org_account_started",
            "organization_id",
            "marketplace_account_id",
            "started_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(
        default=None,
        foreign_key="marketplace_accounts.id",
        nullable=True,
        index=True,
    )
    sync_run_type: str = Field(max_length=32, nullable=False, index=True)
    sync_status: str = Field(max_length=24, nullable=False, index=True)
    records_processed: int = Field(default=0, nullable=False)
    conflicts_detected: int = Field(default=0, nullable=False)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceInventoryConflict(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_conflicts"
    __table_args__ = (
        SAIndex(
            "ix_mkt_inventory_conflict_org_detected",
            "organization_id",
            "detected_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_inventory_conflict_state_detected",
            "marketplace_inventory_state_id",
            "detected_at",
            "id",
        ),
        SAIndex(
            "ix_mkt_inventory_conflict_org_status_detected",
            "organization_id",
            "conflict_status",
            "detected_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_inventory_state_id: int = Field(
        foreign_key="marketplace_inventory_states.id",
        nullable=False,
        index=True,
    )
    conflict_type: str = Field(max_length=40, nullable=False, index=True)
    local_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    marketplace_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    conflict_status: str = Field(max_length=24, nullable=False, index=True)
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceInventorySyncEvent(SQLModel, table=True):
    __tablename__ = "marketplace_inventory_sync_events"
    __table_args__ = (
        SAIndex("ix_mkt_inventory_sync_event_org_created", "organization_id", "created_at", "id"),
        SAIndex(
            "ix_mkt_inventory_sync_event_account_created",
            "marketplace_account_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_mkt_inventory_sync_event_run_created", "sync_run_id", "created_at", "id"),
        SAIndex(
            "ix_mkt_inventory_sync_event_org_type_created",
            "organization_id",
            "event_type",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(
        default=None,
        foreign_key="marketplace_accounts.id",
        nullable=True,
        index=True,
    )
    sync_run_id: int | None = Field(
        default=None,
        foreign_key="marketplace_inventory_sync_runs.id",
        nullable=True,
        index=True,
    )
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
