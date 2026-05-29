from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceEvent(SQLModel, table=True):
    __tablename__ = "marketplace_events"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_account_id",
            "external_event_identifier",
            name="uq_marketplace_event_identity",
        ),
        SAIndex("ix_marketplace_event_org_received", "organization_id", "received_at", "id"),
        SAIndex(
            "ix_marketplace_event_org_account_received",
            "organization_id",
            "marketplace_account_id",
            "received_at",
            "id",
        ),
        SAIndex("ix_marketplace_event_org_status_received", "organization_id", "event_status", "received_at", "id"),
        SAIndex("ix_marketplace_event_org_type_received", "organization_id", "event_type", "received_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    marketplace_type: str = Field(max_length=32, nullable=False, index=True)
    external_event_identifier: str = Field(max_length=255, nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_status: str = Field(max_length=24, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    received_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    processed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceWebhookEndpoint(SQLModel, table=True):
    __tablename__ = "marketplace_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("organization_id", "endpoint_identifier", name="uq_marketplace_webhook_endpoint_identity"),
        SAIndex("ix_marketplace_webhook_endpoint_org_created", "organization_id", "created_at", "id"),
        SAIndex(
            "ix_marketplace_webhook_endpoint_org_status_created",
            "organization_id",
            "endpoint_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    endpoint_type: str = Field(max_length=32, nullable=False, index=True)
    endpoint_status: str = Field(max_length=24, nullable=False, index=True)
    endpoint_identifier: str = Field(max_length=255, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceEventProcessingRun(SQLModel, table=True):
    __tablename__ = "marketplace_event_processing_runs"
    __table_args__ = (
        SAIndex("ix_marketplace_event_run_org_started", "organization_id", "started_at", "id"),
        SAIndex("ix_marketplace_event_run_event_started", "marketplace_event_id", "started_at", "id"),
        SAIndex("ix_marketplace_event_run_org_status_started", "organization_id", "processing_status", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_event_id: int = Field(foreign_key="marketplace_events.id", nullable=False, index=True)
    processing_status: str = Field(max_length=24, nullable=False, index=True)
    processing_result_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class MarketplaceEventLineage(SQLModel, table=True):
    __tablename__ = "marketplace_event_lineage"
    __table_args__ = (
        SAIndex("ix_marketplace_event_lineage_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_marketplace_event_lineage_event_created", "marketplace_event_id", "created_at", "id"),
        SAIndex("ix_marketplace_event_lineage_org_type_created", "organization_id", "lineage_event_type", "created_at", "id"),
        SAIndex("ix_marketplace_event_lineage_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_event_id: int | None = Field(default=None, foreign_key="marketplace_events.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    lineage_event_type: str = Field(max_length=80, nullable=False, index=True)
    lineage_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
