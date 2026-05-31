"""add marketplace connector framework

Revision ID: 20260727_0145
Revises: 20260726_0144
Create Date: 2026-07-27 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260727_0145"
down_revision = "20260726_0144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_code", sa.String(length=32), nullable=False),
        sa.Column("marketplace_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_code", name="uq_marketplace_definition_code"),
    )
    op.create_index("ix_marketplace_definition_code", "marketplace_definition", ["marketplace_code"])
    op.create_index("ix_marketplace_definition_created_at", "marketplace_definition", ["created_at"])

    op.create_table(
        "marketplace_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=160), nullable=False),
        sa.Column("account_identifier", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_id", "owner_id", "account_identifier", name="uq_marketplace_account_owner_identifier"),
    )
    op.create_index("ix_marketplace_account_owner_id", "marketplace_account", ["owner_id"])
    op.create_index("ix_marketplace_account_status", "marketplace_account", ["status"])
    op.create_index("ix_marketplace_account_created_at", "marketplace_account", ["created_at"])
    op.create_index(op.f("ix_marketplace_account_marketplace_id"), "marketplace_account", ["marketplace_id"])

    op.create_table(
        "marketplace_credential",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("credential_type", sa.String(length=40), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "credential_type", name="uq_marketplace_credential_account_type"),
    )
    op.create_index(op.f("ix_marketplace_credential_account_id"), "marketplace_credential", ["account_id"])

    op.create_table(
        "marketplace_capability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("capability_code", sa.String(length=64), nullable=False),
        sa.Column("capability_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_id", "capability_code", name="uq_marketplace_capability_code"),
    )
    op.create_index(op.f("ix_marketplace_capability_marketplace_id"), "marketplace_capability", ["marketplace_id"])

    op.create_table(
        "marketplace_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("execution_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_marketplace_execution_uuid"),
    )
    op.create_index("ix_marketplace_execution_uuid", "marketplace_execution", ["execution_uuid"])
    op.create_index("ix_marketplace_execution_status", "marketplace_execution", ["status"])
    op.create_index("ix_marketplace_execution_created_at", "marketplace_execution", ["created_at"])
    op.create_index(op.f("ix_marketplace_execution_account_id"), "marketplace_execution", ["account_id"])
    op.create_index(op.f("ix_marketplace_execution_marketplace_id"), "marketplace_execution", ["marketplace_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_execution_marketplace_id"), table_name="marketplace_execution")
    op.drop_index(op.f("ix_marketplace_execution_account_id"), table_name="marketplace_execution")
    op.drop_index("ix_marketplace_execution_created_at", table_name="marketplace_execution")
    op.drop_index("ix_marketplace_execution_status", table_name="marketplace_execution")
    op.drop_index("ix_marketplace_execution_uuid", table_name="marketplace_execution")
    op.drop_table("marketplace_execution")

    op.drop_index(op.f("ix_marketplace_capability_marketplace_id"), table_name="marketplace_capability")
    op.drop_table("marketplace_capability")

    op.drop_index(op.f("ix_marketplace_credential_account_id"), table_name="marketplace_credential")
    op.drop_table("marketplace_credential")

    op.drop_index(op.f("ix_marketplace_account_marketplace_id"), table_name="marketplace_account")
    op.drop_index("ix_marketplace_account_created_at", table_name="marketplace_account")
    op.drop_index("ix_marketplace_account_status", table_name="marketplace_account")
    op.drop_index("ix_marketplace_account_owner_id", table_name="marketplace_account")
    op.drop_table("marketplace_account")

    op.drop_index("ix_marketplace_definition_created_at", table_name="marketplace_definition")
    op.drop_index("ix_marketplace_definition_code", table_name="marketplace_definition")
    op.drop_table("marketplace_definition")
