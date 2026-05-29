"""add marketplace account foundation

Revision ID: 20260703_0121
Revises: 20260702_0120
Create Date: 2026-07-03 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260703_0121"
down_revision = "20260702_0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_type", sa.String(length=32), nullable=False),
        sa.Column("marketplace_account_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("account_status", sa.String(length=24), nullable=False),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_type", "marketplace_account_id", name="uq_marketplace_account_identity"),
    )
    op.create_index("ix_marketplace_account_org_type_created", "marketplace_accounts", ["organization_id", "marketplace_type", "created_at", "id"])
    op.create_index("ix_marketplace_account_org_status_created", "marketplace_accounts", ["organization_id", "account_status", "created_at", "id"])
    op.create_index(
        "ix_marketplace_account_org_verification_created",
        "marketplace_accounts",
        ["organization_id", "verification_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_accounts_account_status"), "marketplace_accounts", ["account_status"])
    op.create_index(op.f("ix_marketplace_accounts_marketplace_account_id"), "marketplace_accounts", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_accounts_marketplace_type"), "marketplace_accounts", ["marketplace_type"])
    op.create_index(op.f("ix_marketplace_accounts_organization_id"), "marketplace_accounts", ["organization_id"])
    op.create_index(op.f("ix_marketplace_accounts_verification_status"), "marketplace_accounts", ["verification_status"])

    op.create_table(
        "marketplace_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("credential_type", sa.String(length=32), nullable=False),
        sa.Column("credential_reference", sa.String(length=255), nullable=False),
        sa.Column("credential_status", sa.String(length=24), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "marketplace_account_id",
            "credential_type",
            "credential_reference",
            name="uq_marketplace_credential_reference",
        ),
    )
    op.create_index("ix_marketplace_credential_account_created", "marketplace_credentials", ["marketplace_account_id", "created_at", "id"])
    op.create_index(
        "ix_marketplace_credential_account_status_created",
        "marketplace_credentials",
        ["marketplace_account_id", "credential_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_credentials_credential_status"), "marketplace_credentials", ["credential_status"])
    op.create_index(op.f("ix_marketplace_credentials_credential_type"), "marketplace_credentials", ["credential_type"])
    op.create_index(op.f("ix_marketplace_credentials_marketplace_account_id"), "marketplace_credentials", ["marketplace_account_id"])

    op.create_table(
        "marketplace_connection_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_conn_event_org_created", "marketplace_connection_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_marketplace_conn_event_account_created",
        "marketplace_connection_events",
        ["marketplace_account_id", "created_at", "id"],
    )
    op.create_index(
        "ix_marketplace_conn_event_org_type_created",
        "marketplace_connection_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_marketplace_conn_event_actor_created", "marketplace_connection_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_marketplace_connection_events_actor_user_id"), "marketplace_connection_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_connection_events_event_type"), "marketplace_connection_events", ["event_type"])
    op.create_index(
        op.f("ix_marketplace_connection_events_marketplace_account_id"),
        "marketplace_connection_events",
        ["marketplace_account_id"],
    )
    op.create_index(op.f("ix_marketplace_connection_events_organization_id"), "marketplace_connection_events", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_connection_events_organization_id"), table_name="marketplace_connection_events")
    op.drop_index(op.f("ix_marketplace_connection_events_marketplace_account_id"), table_name="marketplace_connection_events")
    op.drop_index(op.f("ix_marketplace_connection_events_event_type"), table_name="marketplace_connection_events")
    op.drop_index(op.f("ix_marketplace_connection_events_actor_user_id"), table_name="marketplace_connection_events")
    op.drop_index("ix_marketplace_conn_event_actor_created", table_name="marketplace_connection_events")
    op.drop_index("ix_marketplace_conn_event_org_type_created", table_name="marketplace_connection_events")
    op.drop_index("ix_marketplace_conn_event_account_created", table_name="marketplace_connection_events")
    op.drop_index("ix_marketplace_conn_event_org_created", table_name="marketplace_connection_events")
    op.drop_table("marketplace_connection_events")

    op.drop_index(op.f("ix_marketplace_credentials_marketplace_account_id"), table_name="marketplace_credentials")
    op.drop_index(op.f("ix_marketplace_credentials_credential_type"), table_name="marketplace_credentials")
    op.drop_index(op.f("ix_marketplace_credentials_credential_status"), table_name="marketplace_credentials")
    op.drop_index("ix_marketplace_credential_account_status_created", table_name="marketplace_credentials")
    op.drop_index("ix_marketplace_credential_account_created", table_name="marketplace_credentials")
    op.drop_table("marketplace_credentials")

    op.drop_index(op.f("ix_marketplace_accounts_verification_status"), table_name="marketplace_accounts")
    op.drop_index(op.f("ix_marketplace_accounts_organization_id"), table_name="marketplace_accounts")
    op.drop_index(op.f("ix_marketplace_accounts_marketplace_type"), table_name="marketplace_accounts")
    op.drop_index(op.f("ix_marketplace_accounts_marketplace_account_id"), table_name="marketplace_accounts")
    op.drop_index(op.f("ix_marketplace_accounts_account_status"), table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_account_org_verification_created", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_account_org_status_created", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_account_org_type_created", table_name="marketplace_accounts")
    op.drop_table("marketplace_accounts")
