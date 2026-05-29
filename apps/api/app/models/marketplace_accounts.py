from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceAccount(SQLModel, table=True):
    __tablename__ = "marketplace_accounts"
    __table_args__ = (
        UniqueConstraint("marketplace_type", "marketplace_account_id", name="uq_marketplace_account_identity"),
        SAIndex("ix_marketplace_account_org_type_created", "organization_id", "marketplace_type", "created_at", "id"),
        SAIndex("ix_marketplace_account_org_status_created", "organization_id", "account_status", "created_at", "id"),
        SAIndex(
            "ix_marketplace_account_org_verification_created",
            "organization_id",
            "verification_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_type: str = Field(max_length=32, nullable=False, index=True)
    marketplace_account_id: str = Field(max_length=128, nullable=False, index=True)
    display_name: str = Field(max_length=200, nullable=False)
    account_status: str = Field(max_length=24, nullable=False, index=True)
    verification_status: str = Field(max_length=24, nullable=False, index=True)
    connected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    disconnected_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceCredential(SQLModel, table=True):
    __tablename__ = "marketplace_credentials"
    __table_args__ = (
        UniqueConstraint(
            "marketplace_account_id",
            "credential_type",
            "credential_reference",
            name="uq_marketplace_credential_reference",
        ),
        SAIndex("ix_marketplace_credential_account_created", "marketplace_account_id", "created_at", "id"),
        SAIndex(
            "ix_marketplace_credential_account_status_created",
            "marketplace_account_id",
            "credential_status",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_account_id: int = Field(foreign_key="marketplace_accounts.id", nullable=False, index=True)
    credential_type: str = Field(max_length=32, nullable=False, index=True)
    credential_reference: str = Field(max_length=255, nullable=False)
    credential_status: str = Field(max_length=24, nullable=False, index=True)
    rotated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceConnectionEvent(SQLModel, table=True):
    __tablename__ = "marketplace_connection_events"
    __table_args__ = (
        SAIndex("ix_marketplace_conn_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_marketplace_conn_event_account_created", "marketplace_account_id", "created_at", "id"),
        SAIndex("ix_marketplace_conn_event_org_type_created", "organization_id", "event_type", "created_at", "id"),
        SAIndex("ix_marketplace_conn_event_actor_created", "actor_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_accounts.id", nullable=True, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    event_type: str = Field(max_length=80, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
