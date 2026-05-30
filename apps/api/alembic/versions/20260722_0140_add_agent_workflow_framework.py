"""add agent workflow framework

Revision ID: 20260722_0140
Revises: 20260721_0139
Create Date: 2026-07-22 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260722_0140"
down_revision = "20260721_0139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_code", sa.String(length=80), nullable=False),
        sa.Column("workflow_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False),
        sa.Column("cron_expression", sa.String(length=120), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_code", name="uq_workflow_definition_code"),
    )
    op.create_index("ix_workflow_definition_created", "workflow_definition", ["created_at", "id"])
    op.create_index("ix_workflow_definition_enabled_created", "workflow_definition", ["enabled", "created_at", "id"])
    op.create_index("ix_workflow_definition_schedule_next", "workflow_definition", ["schedule_enabled", "next_run_at", "id"])
    op.create_index(op.f("ix_workflow_definition_workflow_code"), "workflow_definition", ["workflow_code"])

    op.create_table(
        "workflow_step",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("agent_definition_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=160), nullable=False),
        sa.Column("step_code", sa.String(length=80), nullable=False),
        sa.Column("required_success", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["agent_definition_id"], ["agent_definition.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "step_order", name="uq_workflow_step_order"),
        sa.UniqueConstraint("workflow_id", "step_code", name="uq_workflow_step_code"),
    )
    op.create_index("ix_workflow_step_workflow_order", "workflow_step", ["workflow_id", "step_order", "id"])
    op.create_index(op.f("ix_workflow_step_workflow_id"), "workflow_step", ["workflow_id"])
    op.create_index(op.f("ix_workflow_step_step_order"), "workflow_step", ["step_order"])
    op.create_index(op.f("ix_workflow_step_agent_definition_id"), "workflow_step", ["agent_definition_id"])
    op.create_index(op.f("ix_workflow_step_step_code"), "workflow_step", ["step_code"])

    op.create_table(
        "workflow_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=False),
        sa.Column("trigger_source", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_workflow_execution_uuid"),
    )
    op.create_index("ix_workflow_execution_workflow_started", "workflow_execution", ["workflow_id", "started_at", "id"])
    op.create_index("ix_workflow_execution_status_started", "workflow_execution", ["status", "started_at", "id"])
    op.create_index(op.f("ix_workflow_execution_workflow_id"), "workflow_execution", ["workflow_id"])
    op.create_index(op.f("ix_workflow_execution_execution_uuid"), "workflow_execution", ["execution_uuid"])
    op.create_index(op.f("ix_workflow_execution_status"), "workflow_execution", ["status"])
    op.create_index(op.f("ix_workflow_execution_started_at"), "workflow_execution", ["started_at"])

    op.create_table(
        "workflow_step_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_execution_id", sa.Integer(), nullable=False),
        sa.Column("workflow_step_id", sa.Integer(), nullable=False),
        sa.Column("agent_execution_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["agent_execution_id"], ["agent_execution.id"]),
        sa.ForeignKeyConstraint(["workflow_execution_id"], ["workflow_execution.id"]),
        sa.ForeignKeyConstraint(["workflow_step_id"], ["workflow_step.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_execution_id", "workflow_step_id", name="uq_workflow_step_execution_edge"),
        sa.UniqueConstraint("agent_execution_id", name="uq_workflow_step_execution_agent_execution"),
    )
    op.create_index("ix_workflow_step_execution_workflow_started", "workflow_step_execution", ["workflow_execution_id", "started_at", "id"])
    op.create_index("ix_workflow_step_execution_status_started", "workflow_step_execution", ["status", "started_at", "id"])
    op.create_index(op.f("ix_workflow_step_execution_workflow_execution_id"), "workflow_step_execution", ["workflow_execution_id"])
    op.create_index(op.f("ix_workflow_step_execution_workflow_step_id"), "workflow_step_execution", ["workflow_step_id"])
    op.create_index(op.f("ix_workflow_step_execution_agent_execution_id"), "workflow_step_execution", ["agent_execution_id"])
    op.create_index(op.f("ix_workflow_step_execution_status"), "workflow_step_execution", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_step_execution_status"), table_name="workflow_step_execution")
    op.drop_index(op.f("ix_workflow_step_execution_agent_execution_id"), table_name="workflow_step_execution")
    op.drop_index(op.f("ix_workflow_step_execution_workflow_step_id"), table_name="workflow_step_execution")
    op.drop_index(op.f("ix_workflow_step_execution_workflow_execution_id"), table_name="workflow_step_execution")
    op.drop_index("ix_workflow_step_execution_status_started", table_name="workflow_step_execution")
    op.drop_index("ix_workflow_step_execution_workflow_started", table_name="workflow_step_execution")
    op.drop_table("workflow_step_execution")

    op.drop_index(op.f("ix_workflow_execution_started_at"), table_name="workflow_execution")
    op.drop_index(op.f("ix_workflow_execution_status"), table_name="workflow_execution")
    op.drop_index(op.f("ix_workflow_execution_execution_uuid"), table_name="workflow_execution")
    op.drop_index(op.f("ix_workflow_execution_workflow_id"), table_name="workflow_execution")
    op.drop_index("ix_workflow_execution_status_started", table_name="workflow_execution")
    op.drop_index("ix_workflow_execution_workflow_started", table_name="workflow_execution")
    op.drop_table("workflow_execution")

    op.drop_index(op.f("ix_workflow_step_step_code"), table_name="workflow_step")
    op.drop_index(op.f("ix_workflow_step_agent_definition_id"), table_name="workflow_step")
    op.drop_index(op.f("ix_workflow_step_step_order"), table_name="workflow_step")
    op.drop_index(op.f("ix_workflow_step_workflow_id"), table_name="workflow_step")
    op.drop_index("ix_workflow_step_workflow_order", table_name="workflow_step")
    op.drop_table("workflow_step")

    op.drop_index(op.f("ix_workflow_definition_workflow_code"), table_name="workflow_definition")
    op.drop_index("ix_workflow_definition_schedule_next", table_name="workflow_definition")
    op.drop_index("ix_workflow_definition_enabled_created", table_name="workflow_definition")
    op.drop_index("ix_workflow_definition_created", table_name="workflow_definition")
    op.drop_table("workflow_definition")
