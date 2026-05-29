from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationRole(SQLModel, table=True):
    __tablename__ = "organization_roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "role_key", name="uq_organization_role_org_key"),
        SAIndex("ix_organization_role_org_created", "organization_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    role_key: str = Field(max_length=32, nullable=False, index=True)
    display_name: str = Field(max_length=80, nullable=False)
    system_managed: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationMembershipRole(SQLModel, table=True):
    __tablename__ = "organization_membership_roles"
    __table_args__ = (
        UniqueConstraint("organization_member_id", "organization_role_id", name="uq_org_member_role_assignment"),
        SAIndex("ix_org_member_role_member_assigned", "organization_member_id", "assigned_at", "id"),
        SAIndex("ix_org_member_role_role_assigned", "organization_role_id", "assigned_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_member_id: int = Field(foreign_key="organization_members.id", nullable=False, index=True)
    organization_role_id: int = Field(foreign_key="organization_roles.id", nullable=False, index=True)
    assigned_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    assigned_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationPermissionAudit(SQLModel, table=True):
    __tablename__ = "organization_permission_audits"
    __table_args__ = (
        SAIndex("ix_org_perm_audit_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_perm_audit_actor_created", "actor_user_id", "created_at", "id"),
        SAIndex("ix_org_perm_audit_target_created", "target_user_id", "created_at", "id"),
        SAIndex("ix_org_perm_audit_action_created", "action_key", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    target_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    action_key: str = Field(max_length=64, nullable=False, index=True)
    permission_result: str = Field(max_length=24, nullable=False, index=True)
    evaluation_context_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
