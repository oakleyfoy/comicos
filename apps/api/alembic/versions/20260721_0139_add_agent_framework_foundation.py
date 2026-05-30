"""add agent framework foundation

Revision ID: 20260721_0139
Revises: 20260720_0138
Create Date: 2026-07-21 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260721_0139"
down_revision = "20260720_0138"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_agent_definition_code"),
    )
    op.create_index("ix_agent_definition_created", "agent_definition", ["created_at", "id"])
    op.create_index("ix_agent_definition_enabled_created", "agent_definition", ["enabled", "created_at", "id"])
    op.create_index(op.f("ix_agent_definition_code"), "agent_definition", ["code"])

    op.create_table(
        "agent_capability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("capability_code", sa.String(length=80), nullable=False),
        sa.Column("capability_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "capability_code", name="uq_agent_capability_agent_code"),
    )
    op.create_index("ix_agent_capability_agent_code", "agent_capability", ["agent_id", "capability_code", "id"])
    op.create_index(op.f("ix_agent_capability_agent_id"), "agent_capability", ["agent_id"])
    op.create_index(op.f("ix_agent_capability_capability_code"), "agent_capability", ["capability_code"])

    op.create_table(
        "agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=False),
        sa.Column("trigger_source", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_agent_execution_uuid"),
    )
    op.create_index("ix_agent_execution_agent_started", "agent_execution", ["agent_id", "started_at", "id"])
    op.create_index("ix_agent_execution_status_started", "agent_execution", ["status", "started_at", "id"])
    op.create_index(op.f("ix_agent_execution_agent_id"), "agent_execution", ["agent_id"])
    op.create_index(op.f("ix_agent_execution_execution_uuid"), "agent_execution", ["execution_uuid"])
    op.create_index(op.f("ix_agent_execution_status"), "agent_execution", ["status"])
    op.create_index(op.f("ix_agent_execution_started_at"), "agent_execution", ["started_at"])

    op.create_table(
        "agent_execution_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["agent_execution.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_execution_event_execution_timestamp", "agent_execution_event", ["execution_id", "event_timestamp", "id"])
    op.create_index("ix_agent_execution_event_type_timestamp", "agent_execution_event", ["event_type", "event_timestamp", "id"])
    op.create_index(op.f("ix_agent_execution_event_execution_id"), "agent_execution_event", ["execution_id"])
    op.create_index(op.f("ix_agent_execution_event_event_type"), "agent_execution_event", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_execution_event_event_type"), table_name="agent_execution_event")
    op.drop_index(op.f("ix_agent_execution_event_execution_id"), table_name="agent_execution_event")
    op.drop_index("ix_agent_execution_event_type_timestamp", table_name="agent_execution_event")
    op.drop_index("ix_agent_execution_event_execution_timestamp", table_name="agent_execution_event")
    op.drop_table("agent_execution_event")

    op.drop_index(op.f("ix_agent_execution_started_at"), table_name="agent_execution")
    op.drop_index(op.f("ix_agent_execution_status"), table_name="agent_execution")
    op.drop_index(op.f("ix_agent_execution_execution_uuid"), table_name="agent_execution")
    op.drop_index(op.f("ix_agent_execution_agent_id"), table_name="agent_execution")
    op.drop_index("ix_agent_execution_status_started", table_name="agent_execution")
    op.drop_index("ix_agent_execution_agent_started", table_name="agent_execution")
    op.drop_table("agent_execution")

    op.drop_index(op.f("ix_agent_capability_capability_code"), table_name="agent_capability")
    op.drop_index(op.f("ix_agent_capability_agent_id"), table_name="agent_capability")
    op.drop_index("ix_agent_capability_agent_code", table_name="agent_capability")
    op.drop_table("agent_capability")

    op.drop_index(op.f("ix_agent_definition_code"), table_name="agent_definition")
    op.drop_index("ix_agent_definition_enabled_created", table_name="agent_definition")
    op.drop_index("ix_agent_definition_created", table_name="agent_definition")
    op.drop_table("agent_definition")
