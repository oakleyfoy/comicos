from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_organization_public_id"),
        UniqueConstraint("slug", name="uq_organization_slug"),
        SAIndex("ix_organization_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_organization_status_updated", "status", "updated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    public_id: str = Field(max_length=48, nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    display_name: str = Field(max_length=200, nullable=False)
    slug: str = Field(max_length=120, nullable=False, index=True)
    organization_type: str = Field(max_length=24, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OrganizationMember(SQLModel, table=True):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member_org_user"),
        SAIndex("ix_organization_member_org_status", "organization_id", "membership_status", "joined_at", "id"),
        SAIndex("ix_organization_member_user_status", "user_id", "membership_status", "joined_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    membership_status: str = Field(max_length=24, nullable=False, index=True)
    joined_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    invited_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    removed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class OrganizationInvitation(SQLModel, table=True):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        UniqueConstraint("invitation_token", name="uq_organization_invitation_token"),
        SAIndex("ix_organization_invitation_org_status", "organization_id", "status", "created_at", "id"),
        SAIndex("ix_organization_invitation_email_status", "email", "status", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    email: str = Field(max_length=320, nullable=False, index=True)
    invitation_token: str = Field(max_length=96, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    accepted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    invited_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
