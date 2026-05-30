"""add agent security permissions

Revision ID: 20260725_0143
Revises: 20260724_0142
Create Date: 2026-07-25 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260725_0143"
down_revision = "20260724_0142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_permission_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("capability_code", sa.String(length=120), nullable=False),
        sa.Column("permission_scope", sa.String(length=24), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "capability_code", "permission_scope", name="uq_agent_permission_policy_edge"),
    )
    op.create_index(
        "ix_agent_permission_policy_agent_scope",
        "agent_permission_policy",
        ["agent_id", "permission_scope", "id"],
    )
    op.create_index(
        "ix_agent_permission_policy_capability_scope",
        "agent_permission_policy",
        ["capability_code", "permission_scope", "id"],
    )
    op.create_index(
        "ix_agent_permission_policy_allowed_updated",
        "agent_permission_policy",
        ["allowed", "updated_at", "id"],
    )
    op.create_index(op.f("ix_agent_permission_policy_agent_id"), "agent_permission_policy", ["agent_id"])
    op.create_index(op.f("ix_agent_permission_policy_capability_code"), "agent_permission_policy", ["capability_code"])
    op.create_index(op.f("ix_agent_permission_policy_permission_scope"), "agent_permission_policy", ["permission_scope"])

    op.create_table(
        "agent_permission_audit_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("capability_code", sa.String(length=120), nullable=False),
        sa.Column("action_code", sa.String(length=120), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_definition.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["agent_execution.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_permission_audit_agent_created",
        "agent_permission_audit_event",
        ["agent_id", "created_at", "id"],
    )
    op.create_index(
        "ix_agent_permission_audit_capability_created",
        "agent_permission_audit_event",
        ["capability_code", "created_at", "id"],
    )
    op.create_index(
        "ix_agent_permission_audit_decision_created",
        "agent_permission_audit_event",
        ["decision", "created_at", "id"],
    )
    op.create_index(
        "ix_agent_permission_audit_execution_created",
        "agent_permission_audit_event",
        ["execution_id", "created_at", "id"],
    )
    op.create_index(op.f("ix_agent_permission_audit_event_agent_id"), "agent_permission_audit_event", ["agent_id"])
    op.create_index(op.f("ix_agent_permission_audit_event_execution_id"), "agent_permission_audit_event", ["execution_id"])
    op.create_index(op.f("ix_agent_permission_audit_event_capability_code"), "agent_permission_audit_event", ["capability_code"])
    op.create_index(op.f("ix_agent_permission_audit_event_action_code"), "agent_permission_audit_event", ["action_code"])
    op.create_index(op.f("ix_agent_permission_audit_event_decision"), "agent_permission_audit_event", ["decision"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_permission_audit_event_decision"), table_name="agent_permission_audit_event")
    op.drop_index(op.f("ix_agent_permission_audit_event_action_code"), table_name="agent_permission_audit_event")
    op.drop_index(op.f("ix_agent_permission_audit_event_capability_code"), table_name="agent_permission_audit_event")
    op.drop_index(op.f("ix_agent_permission_audit_event_execution_id"), table_name="agent_permission_audit_event")
    op.drop_index(op.f("ix_agent_permission_audit_event_agent_id"), table_name="agent_permission_audit_event")
    op.drop_index("ix_agent_permission_audit_execution_created", table_name="agent_permission_audit_event")
    op.drop_index("ix_agent_permission_audit_decision_created", table_name="agent_permission_audit_event")
    op.drop_index("ix_agent_permission_audit_capability_created", table_name="agent_permission_audit_event")
    op.drop_index("ix_agent_permission_audit_agent_created", table_name="agent_permission_audit_event")
    op.drop_table("agent_permission_audit_event")

    op.drop_index(op.f("ix_agent_permission_policy_permission_scope"), table_name="agent_permission_policy")
    op.drop_index(op.f("ix_agent_permission_policy_capability_code"), table_name="agent_permission_policy")
    op.drop_index(op.f("ix_agent_permission_policy_agent_id"), table_name="agent_permission_policy")
    op.drop_index("ix_agent_permission_policy_allowed_updated", table_name="agent_permission_policy")
    op.drop_index("ix_agent_permission_policy_capability_scope", table_name="agent_permission_policy")
    op.drop_index("ix_agent_permission_policy_agent_scope", table_name="agent_permission_policy")
    op.drop_table("agent_permission_policy")
