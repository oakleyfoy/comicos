"""add auth session security context

Revision ID: 20260626_0114
Revises: 20260625_0113
Create Date: 2026-06-26 00:14:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260626_0114"
down_revision = "20260625_0113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=False),
        sa.Column("device_type", sa.String(length=24), nullable=False),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("session_status", sa.String(length=24), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash", name="uq_user_auth_session_token_hash"),
    )
    op.create_index("ix_user_auth_session_user_issued", "user_auth_sessions", ["user_id", "issued_at", "id"])
    op.create_index("ix_user_auth_session_user_status", "user_auth_sessions", ["user_id", "session_status", "id"])
    op.create_index("ix_user_auth_session_org_seen", "user_auth_sessions", ["organization_id", "last_seen_at", "id"])

    op.create_table(
        "user_auth_session_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_session_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["auth_session_id"], ["user_auth_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_auth_session_event_session_created", "user_auth_session_events", ["auth_session_id", "created_at", "id"])
    op.create_index("ix_user_auth_session_event_user_created", "user_auth_session_events", ["user_id", "created_at", "id"])
    op.create_index("ix_user_auth_session_event_org_created", "user_auth_session_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_user_auth_session_event_type_created", "user_auth_session_events", ["event_type", "created_at", "id"])

    op.create_table(
        "organization_security_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("active_organization_id", sa.Integer(), nullable=True),
        sa.Column("last_org_switch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["active_organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_org_security_context_user"),
    )
    op.create_index("ix_org_security_context_active_org", "organization_security_contexts", ["active_organization_id", "updated_at", "id"])


def downgrade() -> None:
    op.drop_table("organization_security_contexts")
    op.drop_table("user_auth_session_events")
    op.drop_table("user_auth_sessions")
