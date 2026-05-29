from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserAuthSession(SQLModel, table=True):
    __tablename__ = "user_auth_sessions"
    __table_args__ = (
        UniqueConstraint("session_token_hash", name="uq_user_auth_session_token_hash"),
        SAIndex("ix_user_auth_session_user_issued", "user_id", "issued_at", "id"),
        SAIndex("ix_user_auth_session_user_status", "user_id", "session_status", "id"),
        SAIndex("ix_user_auth_session_org_seen", "organization_id", "last_seen_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    session_token_hash: str = Field(max_length=64, nullable=False, index=True)
    device_label: str = Field(max_length=120, nullable=False)
    device_type: str = Field(max_length=24, nullable=False, index=True)
    ip_address: str | None = Field(default=None, max_length=128, nullable=True)
    user_agent: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    organization_id: int | None = Field(default=None, foreign_key="organizations.id", nullable=True, index=True)
    session_status: str = Field(max_length=24, nullable=False, index=True)
    issued_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    last_seen_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class UserAuthSessionEvent(SQLModel, table=True):
    __tablename__ = "user_auth_session_events"
    __table_args__ = (
        SAIndex("ix_user_auth_session_event_session_created", "auth_session_id", "created_at", "id"),
        SAIndex("ix_user_auth_session_event_user_created", "user_id", "created_at", "id"),
        SAIndex("ix_user_auth_session_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_user_auth_session_event_type_created", "event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    auth_session_id: int | None = Field(default=None, foreign_key="user_auth_sessions.id", nullable=True, index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    organization_id: int | None = Field(default=None, foreign_key="organizations.id", nullable=True, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationSecurityContext(SQLModel, table=True):
    __tablename__ = "organization_security_contexts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_org_security_context_user"),
        SAIndex("ix_org_security_context_active_org", "active_organization_id", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    active_organization_id: int | None = Field(default=None, foreign_key="organizations.id", nullable=True, index=True)
    last_org_switch_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
