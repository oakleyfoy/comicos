from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceDefinition(SQLModel, table=True):
    __tablename__ = "marketplace_definition"
    __table_args__ = (
        UniqueConstraint("marketplace_code", name="uq_marketplace_definition_code"),
        SAIndex("ix_marketplace_definition_code", "marketplace_code"),
        SAIndex("ix_marketplace_definition_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_code: str = Field(max_length=32, nullable=False)
    marketplace_name: str = Field(max_length=120, nullable=False)
    description: str | None = Field(default=None, max_length=500, nullable=True)
    enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceAccount(SQLModel, table=True):
    __tablename__ = "marketplace_account"
    __table_args__ = (
        UniqueConstraint("marketplace_id", "owner_id", "account_identifier", name="uq_marketplace_account_owner_identifier"),
        SAIndex("ix_marketplace_account_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_id: int = Field(foreign_key="marketplace_definition.id", nullable=False, index=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    account_name: str = Field(max_length=160, nullable=False)
    account_identifier: str = Field(max_length=160, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceCredential(SQLModel, table=True):
    __tablename__ = "marketplace_credential"
    __table_args__ = (
        UniqueConstraint("account_id", "credential_type", name="uq_marketplace_credential_account_type"),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="marketplace_account.id", nullable=False, index=True)
    credential_type: str = Field(max_length=40, nullable=False)
    encrypted_payload: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceCapability(SQLModel, table=True):
    __tablename__ = "marketplace_capability"
    __table_args__ = (
        UniqueConstraint("marketplace_id", "capability_code", name="uq_marketplace_capability_code"),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_id: int = Field(foreign_key="marketplace_definition.id", nullable=False, index=True)
    capability_code: str = Field(max_length=64, nullable=False)
    capability_name: str = Field(max_length=160, nullable=False)


class MarketplaceExecution(SQLModel, table=True):
    __tablename__ = "marketplace_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_marketplace_execution_uuid"),
        SAIndex("ix_marketplace_execution_uuid", "execution_uuid"),
        SAIndex("ix_marketplace_execution_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    marketplace_id: int = Field(foreign_key="marketplace_definition.id", nullable=False, index=True)
    account_id: int | None = Field(default=None, foreign_key="marketplace_account.id", nullable=True, index=True)
    execution_uuid: str = Field(max_length=64, nullable=False)
    execution_type: str = Field(max_length=80, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
