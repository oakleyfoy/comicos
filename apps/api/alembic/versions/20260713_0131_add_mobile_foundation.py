"""add mobile foundation

Revision ID: 20260713_0131
Revises: 20260712_0130
Create Date: 2026-07-13 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260713_0131"
down_revision = "20260712_0130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("device_identifier", sa.String(length=128), nullable=False),
        sa.Column("device_name", sa.String(length=200), nullable=False),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.Column("device_status", sa.String(length=24), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "device_identifier", name="uq_mobile_device_org_identifier"),
    )
    op.create_index("ix_mobile_device_org_created", "mobile_devices", ["organization_id", "created_at", "id"])
    op.create_index("ix_mobile_device_org_status_created", "mobile_devices", ["organization_id", "device_status", "created_at", "id"])
    op.create_index(op.f("ix_mobile_devices_organization_id"), "mobile_devices", ["organization_id"])
    op.create_index(op.f("ix_mobile_devices_device_identifier"), "mobile_devices", ["device_identifier"])
    op.create_index(op.f("ix_mobile_devices_device_type"), "mobile_devices", ["device_type"])
    op.create_index(op.f("ix_mobile_devices_device_status"), "mobile_devices", ["device_status"])

    op.create_table(
        "mobile_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_session_org_started", "mobile_sessions", ["organization_id", "started_at", "id"])
    op.create_index("ix_mobile_session_device_started", "mobile_sessions", ["device_id", "started_at", "id"])
    op.create_index("ix_mobile_session_org_status_started", "mobile_sessions", ["organization_id", "session_status", "started_at", "id"])
    op.create_index(op.f("ix_mobile_sessions_organization_id"), "mobile_sessions", ["organization_id"])
    op.create_index(op.f("ix_mobile_sessions_device_id"), "mobile_sessions", ["device_id"])
    op.create_index(op.f("ix_mobile_sessions_user_id"), "mobile_sessions", ["user_id"])
    op.create_index(op.f("ix_mobile_sessions_session_status"), "mobile_sessions", ["session_status"])

    op.create_table(
        "offline_sync_contracts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("contract_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offline_sync_contract_org_created", "offline_sync_contracts", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_offline_sync_contract_org_type_created",
        "offline_sync_contracts",
        ["organization_id", "contract_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_offline_sync_contracts_organization_id"), "offline_sync_contracts", ["organization_id"])
    op.create_index(op.f("ix_offline_sync_contracts_contract_type"), "offline_sync_contracts", ["contract_type"])

    op.create_table(
        "mobile_foundation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_foundation_event_org_created", "mobile_foundation_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_foundation_event_org_type_created",
        "mobile_foundation_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_mobile_foundation_event_actor_created", "mobile_foundation_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_mobile_foundation_events_organization_id"), "mobile_foundation_events", ["organization_id"])
    op.create_index(op.f("ix_mobile_foundation_events_actor_user_id"), "mobile_foundation_events", ["actor_user_id"])
    op.create_index(op.f("ix_mobile_foundation_events_event_type"), "mobile_foundation_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mobile_foundation_events_event_type"), table_name="mobile_foundation_events")
    op.drop_index(op.f("ix_mobile_foundation_events_actor_user_id"), table_name="mobile_foundation_events")
    op.drop_index(op.f("ix_mobile_foundation_events_organization_id"), table_name="mobile_foundation_events")
    op.drop_index("ix_mobile_foundation_event_actor_created", table_name="mobile_foundation_events")
    op.drop_index("ix_mobile_foundation_event_org_type_created", table_name="mobile_foundation_events")
    op.drop_index("ix_mobile_foundation_event_org_created", table_name="mobile_foundation_events")
    op.drop_table("mobile_foundation_events")

    op.drop_index(op.f("ix_offline_sync_contracts_contract_type"), table_name="offline_sync_contracts")
    op.drop_index(op.f("ix_offline_sync_contracts_organization_id"), table_name="offline_sync_contracts")
    op.drop_index("ix_offline_sync_contract_org_type_created", table_name="offline_sync_contracts")
    op.drop_index("ix_offline_sync_contract_org_created", table_name="offline_sync_contracts")
    op.drop_table("offline_sync_contracts")

    op.drop_index(op.f("ix_mobile_sessions_session_status"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_user_id"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_device_id"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_organization_id"), table_name="mobile_sessions")
    op.drop_index("ix_mobile_session_org_status_started", table_name="mobile_sessions")
    op.drop_index("ix_mobile_session_device_started", table_name="mobile_sessions")
    op.drop_index("ix_mobile_session_org_started", table_name="mobile_sessions")
    op.drop_table("mobile_sessions")

    op.drop_index(op.f("ix_mobile_devices_device_status"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_device_type"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_device_identifier"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_organization_id"), table_name="mobile_devices")
    op.drop_index("ix_mobile_device_org_status_created", table_name="mobile_devices")
    op.drop_index("ix_mobile_device_org_created", table_name="mobile_devices")
    op.drop_table("mobile_devices")
