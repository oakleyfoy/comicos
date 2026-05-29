"""add organization audit ledger foundation

Revision ID: 20260701_0119
Revises: 20260630_0118
Create Date: 2026-07-01 00:19:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_0119"
down_revision = "20260630_0118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_audit_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("audit_category", sa.String(length=32), nullable=False),
        sa.Column("audit_action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("audit_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_audit_ledger_org_created", "organization_audit_ledger", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_org_audit_ledger_org_category_created",
        "organization_audit_ledger",
        ["organization_id", "audit_category", "created_at", "id"],
    )
    op.create_index(
        "ix_org_audit_ledger_org_resource_created",
        "organization_audit_ledger",
        ["organization_id", "resource_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_organization_audit_ledger_actor_user_id"), "organization_audit_ledger", ["actor_user_id"])
    op.create_index(op.f("ix_organization_audit_ledger_audit_action"), "organization_audit_ledger", ["audit_action"])
    op.create_index(op.f("ix_organization_audit_ledger_audit_category"), "organization_audit_ledger", ["audit_category"])
    op.create_index(op.f("ix_organization_audit_ledger_organization_id"), "organization_audit_ledger", ["organization_id"])
    op.create_index(op.f("ix_organization_audit_ledger_resource_id"), "organization_audit_ledger", ["resource_id"])
    op.create_index(op.f("ix_organization_audit_ledger_resource_type"), "organization_audit_ledger", ["resource_type"])

    op.create_table(
        "organization_compliance_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("compliance_event_type", sa.String(length=80), nullable=False),
        sa.Column("severity_level", sa.String(length=16), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_compliance_event_org_created",
        "organization_compliance_events",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_compliance_event_org_severity_created",
        "organization_compliance_events",
        ["organization_id", "severity_level", "created_at", "id"],
    )
    op.create_index(
        "ix_org_compliance_event_org_type_created",
        "organization_compliance_events",
        ["organization_id", "compliance_event_type", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_organization_compliance_events_compliance_event_type"),
        "organization_compliance_events",
        ["compliance_event_type"],
    )
    op.create_index(op.f("ix_organization_compliance_events_organization_id"), "organization_compliance_events", ["organization_id"])
    op.create_index(op.f("ix_organization_compliance_events_severity_level"), "organization_compliance_events", ["severity_level"])

    op.create_table(
        "organization_audit_access_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("accessed_resource_type", sa.String(length=64), nullable=False),
        sa.Column("accessed_resource_id", sa.String(length=128), nullable=True),
        sa.Column("access_result", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_audit_access_log_org_created",
        "organization_audit_access_logs",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_audit_access_log_org_resource_created",
        "organization_audit_access_logs",
        ["organization_id", "accessed_resource_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_organization_audit_access_logs_access_result"), "organization_audit_access_logs", ["access_result"])
    op.create_index(
        op.f("ix_organization_audit_access_logs_accessed_resource_id"),
        "organization_audit_access_logs",
        ["accessed_resource_id"],
    )
    op.create_index(
        op.f("ix_organization_audit_access_logs_accessed_resource_type"),
        "organization_audit_access_logs",
        ["accessed_resource_type"],
    )
    op.create_index(op.f("ix_organization_audit_access_logs_actor_user_id"), "organization_audit_access_logs", ["actor_user_id"])
    op.create_index(op.f("ix_organization_audit_access_logs_organization_id"), "organization_audit_access_logs", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_audit_access_logs_organization_id"), table_name="organization_audit_access_logs")
    op.drop_index(op.f("ix_organization_audit_access_logs_actor_user_id"), table_name="organization_audit_access_logs")
    op.drop_index(op.f("ix_organization_audit_access_logs_accessed_resource_type"), table_name="organization_audit_access_logs")
    op.drop_index(op.f("ix_organization_audit_access_logs_accessed_resource_id"), table_name="organization_audit_access_logs")
    op.drop_index(op.f("ix_organization_audit_access_logs_access_result"), table_name="organization_audit_access_logs")
    op.drop_index("ix_org_audit_access_log_org_resource_created", table_name="organization_audit_access_logs")
    op.drop_index("ix_org_audit_access_log_org_created", table_name="organization_audit_access_logs")
    op.drop_table("organization_audit_access_logs")

    op.drop_index(op.f("ix_organization_compliance_events_severity_level"), table_name="organization_compliance_events")
    op.drop_index(op.f("ix_organization_compliance_events_organization_id"), table_name="organization_compliance_events")
    op.drop_index(op.f("ix_organization_compliance_events_compliance_event_type"), table_name="organization_compliance_events")
    op.drop_index("ix_org_compliance_event_org_type_created", table_name="organization_compliance_events")
    op.drop_index("ix_org_compliance_event_org_severity_created", table_name="organization_compliance_events")
    op.drop_index("ix_org_compliance_event_org_created", table_name="organization_compliance_events")
    op.drop_table("organization_compliance_events")

    op.drop_index(op.f("ix_organization_audit_ledger_resource_type"), table_name="organization_audit_ledger")
    op.drop_index(op.f("ix_organization_audit_ledger_resource_id"), table_name="organization_audit_ledger")
    op.drop_index(op.f("ix_organization_audit_ledger_organization_id"), table_name="organization_audit_ledger")
    op.drop_index(op.f("ix_organization_audit_ledger_audit_category"), table_name="organization_audit_ledger")
    op.drop_index(op.f("ix_organization_audit_ledger_audit_action"), table_name="organization_audit_ledger")
    op.drop_index(op.f("ix_organization_audit_ledger_actor_user_id"), table_name="organization_audit_ledger")
    op.drop_index("ix_org_audit_ledger_org_resource_created", table_name="organization_audit_ledger")
    op.drop_index("ix_org_audit_ledger_org_category_created", table_name="organization_audit_ledger")
    op.drop_index("ix_org_audit_ledger_org_created", table_name="organization_audit_ledger")
    op.drop_table("organization_audit_ledger")
