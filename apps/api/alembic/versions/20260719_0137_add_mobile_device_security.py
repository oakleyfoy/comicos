"""add mobile device security

Revision ID: 20260719_0137
Revises: 20260718_0136
Create Date: 2026-07-19 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260719_0137"
down_revision = "20260718_0136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_device_trust_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("mobile_device_id", sa.Integer(), nullable=False),
        sa.Column("trust_status", sa.String(length=24), nullable=False),
        sa.Column("trust_reason", sa.String(length=255), nullable=True),
        sa.Column("trusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mobile_device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "mobile_device_id", name="uq_mobile_device_trust_org_device"),
    )
    op.create_index("ix_mobile_device_trust_org_created", "mobile_device_trust_states", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_device_trust_org_status_updated",
        "mobile_device_trust_states",
        ["organization_id", "trust_status", "updated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_device_trust_states_organization_id"), "mobile_device_trust_states", ["organization_id"])
    op.create_index(op.f("ix_mobile_device_trust_states_mobile_device_id"), "mobile_device_trust_states", ["mobile_device_id"])
    op.create_index(op.f("ix_mobile_device_trust_states_trust_status"), "mobile_device_trust_states", ["trust_status"])

    op.create_table(
        "mobile_device_security_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("policy_key", sa.String(length=64), nullable=False),
        sa.Column("policy_status", sa.String(length=16), nullable=False),
        sa.Column("policy_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "policy_key", name="uq_mobile_security_policy_org_key"),
    )
    op.create_index("ix_mobile_security_policy_org_created", "mobile_device_security_policies", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_security_policy_org_status_updated",
        "mobile_device_security_policies",
        ["organization_id", "policy_status", "updated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_device_security_policies_organization_id"), "mobile_device_security_policies", ["organization_id"])
    op.create_index(op.f("ix_mobile_device_security_policies_policy_key"), "mobile_device_security_policies", ["policy_key"])
    op.create_index(op.f("ix_mobile_device_security_policies_policy_status"), "mobile_device_security_policies", ["policy_status"])

    op.create_table(
        "mobile_device_access_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("mobile_device_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_result", sa.String(length=16), nullable=False),
        sa.Column("access_reason", sa.String(length=255), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mobile_device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_device_access_org_accessed", "mobile_device_access_logs", ["organization_id", "accessed_at", "id"])
    op.create_index(
        "ix_mobile_device_access_device_accessed",
        "mobile_device_access_logs",
        ["mobile_device_id", "accessed_at", "id"],
    )
    op.create_index(
        "ix_mobile_device_access_org_result_accessed",
        "mobile_device_access_logs",
        ["organization_id", "access_result", "accessed_at", "id"],
    )
    op.create_index(op.f("ix_mobile_device_access_logs_organization_id"), "mobile_device_access_logs", ["organization_id"])
    op.create_index(op.f("ix_mobile_device_access_logs_mobile_device_id"), "mobile_device_access_logs", ["mobile_device_id"])
    op.create_index(op.f("ix_mobile_device_access_logs_user_id"), "mobile_device_access_logs", ["user_id"])
    op.create_index(op.f("ix_mobile_device_access_logs_access_result"), "mobile_device_access_logs", ["access_result"])

    op.create_table(
        "mobile_device_security_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("mobile_device_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["mobile_device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mobile_device_security_event_org_created",
        "mobile_device_security_events",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_mobile_device_security_event_device_created",
        "mobile_device_security_events",
        ["mobile_device_id", "created_at", "id"],
    )
    op.create_index(
        "ix_mobile_device_security_event_org_type_created",
        "mobile_device_security_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_mobile_device_security_events_organization_id"), "mobile_device_security_events", ["organization_id"])
    op.create_index(op.f("ix_mobile_device_security_events_mobile_device_id"), "mobile_device_security_events", ["mobile_device_id"])
    op.create_index(op.f("ix_mobile_device_security_events_actor_user_id"), "mobile_device_security_events", ["actor_user_id"])
    op.create_index(op.f("ix_mobile_device_security_events_event_type"), "mobile_device_security_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mobile_device_security_events_event_type"), table_name="mobile_device_security_events")
    op.drop_index(op.f("ix_mobile_device_security_events_actor_user_id"), table_name="mobile_device_security_events")
    op.drop_index(op.f("ix_mobile_device_security_events_mobile_device_id"), table_name="mobile_device_security_events")
    op.drop_index(op.f("ix_mobile_device_security_events_organization_id"), table_name="mobile_device_security_events")
    op.drop_index("ix_mobile_device_security_event_org_type_created", table_name="mobile_device_security_events")
    op.drop_index("ix_mobile_device_security_event_device_created", table_name="mobile_device_security_events")
    op.drop_index("ix_mobile_device_security_event_org_created", table_name="mobile_device_security_events")
    op.drop_table("mobile_device_security_events")

    op.drop_index(op.f("ix_mobile_device_access_logs_access_result"), table_name="mobile_device_access_logs")
    op.drop_index(op.f("ix_mobile_device_access_logs_user_id"), table_name="mobile_device_access_logs")
    op.drop_index(op.f("ix_mobile_device_access_logs_mobile_device_id"), table_name="mobile_device_access_logs")
    op.drop_index(op.f("ix_mobile_device_access_logs_organization_id"), table_name="mobile_device_access_logs")
    op.drop_index("ix_mobile_device_access_org_result_accessed", table_name="mobile_device_access_logs")
    op.drop_index("ix_mobile_device_access_device_accessed", table_name="mobile_device_access_logs")
    op.drop_index("ix_mobile_device_access_org_accessed", table_name="mobile_device_access_logs")
    op.drop_table("mobile_device_access_logs")

    op.drop_index(op.f("ix_mobile_device_security_policies_policy_status"), table_name="mobile_device_security_policies")
    op.drop_index(op.f("ix_mobile_device_security_policies_policy_key"), table_name="mobile_device_security_policies")
    op.drop_index(op.f("ix_mobile_device_security_policies_organization_id"), table_name="mobile_device_security_policies")
    op.drop_index("ix_mobile_security_policy_org_status_updated", table_name="mobile_device_security_policies")
    op.drop_index("ix_mobile_security_policy_org_created", table_name="mobile_device_security_policies")
    op.drop_table("mobile_device_security_policies")

    op.drop_index(op.f("ix_mobile_device_trust_states_trust_status"), table_name="mobile_device_trust_states")
    op.drop_index(op.f("ix_mobile_device_trust_states_mobile_device_id"), table_name="mobile_device_trust_states")
    op.drop_index(op.f("ix_mobile_device_trust_states_organization_id"), table_name="mobile_device_trust_states")
    op.drop_index("ix_mobile_device_trust_org_status_updated", table_name="mobile_device_trust_states")
    op.drop_index("ix_mobile_device_trust_org_created", table_name="mobile_device_trust_states")
    op.drop_table("mobile_device_trust_states")
