"""add organization foundation

Revision ID: 20260624_0112
Revises: 20260623_0111
Create Date: 2026-06-24 00:12:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260624_0112"
down_revision = "20260623_0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=48), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("organization_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_organization_public_id"),
        sa.UniqueConstraint("slug", name="uq_organization_slug"),
    )
    op.create_index("ix_organization_owner_created", "organizations", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_organization_status_updated", "organizations", ["status", "updated_at", "id"])

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("membership_status", sa.String(length=24), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member_org_user"),
    )
    op.create_index("ix_organization_member_org_status", "organization_members", ["organization_id", "membership_status", "joined_at", "id"])
    op.create_index("ix_organization_member_user_status", "organization_members", ["user_id", "membership_status", "joined_at", "id"])

    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("invitation_token", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_token", name="uq_organization_invitation_token"),
    )
    op.create_index("ix_organization_invitation_org_status", "organization_invitations", ["organization_id", "status", "created_at", "id"])
    op.create_index("ix_organization_invitation_email_status", "organization_invitations", ["email", "status", "created_at", "id"])

    op.create_table(
        "organization_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_event_org_created", "organization_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_organization_event_actor_created", "organization_events", ["actor_user_id", "created_at", "id"])
    op.create_index("ix_organization_event_type_created", "organization_events", ["event_type", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("organization_events")
    op.drop_table("organization_invitations")
    op.drop_table("organization_members")
    op.drop_table("organizations")
