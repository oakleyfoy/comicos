"""add agent analytics metrics

Revision ID: 20260726_0144
Revises: 20260725_0143
Create Date: 2026-07-26 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260726_0144"
down_revision = "20260725_0143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_metric_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_uuid", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_uuid", name="uq_agent_metric_snapshot_uuid"),
    )
    op.create_index("ix_agent_metric_snapshot_date_generated", "agent_metric_snapshot", ["snapshot_date", "generated_at", "id"])
    op.create_index("ix_agent_metric_snapshot_scope_generated", "agent_metric_snapshot", ["scope", "generated_at", "id"])
    op.create_index(op.f("ix_agent_metric_snapshot_snapshot_uuid"), "agent_metric_snapshot", ["snapshot_uuid"])
    op.create_index(op.f("ix_agent_metric_snapshot_snapshot_date"), "agent_metric_snapshot", ["snapshot_date"])
    op.create_index(op.f("ix_agent_metric_snapshot_generated_at"), "agent_metric_snapshot", ["generated_at"])

    op.create_table(
        "agent_performance_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("executions_total", sa.Integer(), nullable=False),
        sa.Column("executions_completed", sa.Integer(), nullable=False),
        sa.Column("executions_failed", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=False),
        sa.Column("avg_duration_ms", sa.Integer(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recommendations_generated", sa.Integer(), nullable=False),
        sa.Column("recommendations_reviewed", sa.Integer(), nullable=False),
        sa.Column("recommendations_accepted", sa.Integer(), nullable=False),
        sa.Column("recommendations_dismissed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_definition.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["agent_metric_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_performance_snapshot_agent", "agent_performance_metric", ["snapshot_id", "agent_code", "id"])
    op.create_index("ix_agent_performance_agent_created", "agent_performance_metric", ["agent_code", "created_at", "id"])
    op.create_index(op.f("ix_agent_performance_metric_snapshot_id"), "agent_performance_metric", ["snapshot_id"])
    op.create_index(op.f("ix_agent_performance_metric_agent_id"), "agent_performance_metric", ["agent_id"])
    op.create_index(op.f("ix_agent_performance_metric_agent_code"), "agent_performance_metric", ["agent_code"])

    op.create_table(
        "workflow_performance_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("workflow_code", sa.String(length=80), nullable=False),
        sa.Column("executions_total", sa.Integer(), nullable=False),
        sa.Column("executions_completed", sa.Integer(), nullable=False),
        sa.Column("executions_failed", sa.Integer(), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=False),
        sa.Column("avg_duration_ms", sa.Integer(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["agent_metric_snapshot.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_performance_snapshot_workflow",
        "workflow_performance_metric",
        ["snapshot_id", "workflow_code", "id"],
    )
    op.create_index("ix_workflow_performance_workflow_created", "workflow_performance_metric", ["workflow_code", "created_at", "id"])
    op.create_index(op.f("ix_workflow_performance_metric_snapshot_id"), "workflow_performance_metric", ["snapshot_id"])
    op.create_index(op.f("ix_workflow_performance_metric_workflow_id"), "workflow_performance_metric", ["workflow_id"])
    op.create_index(op.f("ix_workflow_performance_metric_workflow_code"), "workflow_performance_metric", ["workflow_code"])

    op.create_table(
        "recommendation_outcome_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("recommendations_total", sa.Integer(), nullable=False),
        sa.Column("reviewed_total", sa.Integer(), nullable=False),
        sa.Column("accepted_total", sa.Integer(), nullable=False),
        sa.Column("dismissed_total", sa.Integer(), nullable=False),
        sa.Column("acceptance_rate", sa.Float(), nullable=False),
        sa.Column("dismissal_rate", sa.Float(), nullable=False),
        sa.Column("avg_confidence_score", sa.Float(), nullable=False),
        sa.Column("avg_opportunity_score", sa.Float(), nullable=False),
        sa.Column("avg_priority_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["agent_metric_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_outcome_snapshot_type",
        "recommendation_outcome_metric",
        ["snapshot_id", "recommendation_type", "id"],
    )
    op.create_index(
        "ix_recommendation_outcome_type_created",
        "recommendation_outcome_metric",
        ["recommendation_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_recommendation_outcome_metric_snapshot_id"), "recommendation_outcome_metric", ["snapshot_id"])
    op.create_index(
        op.f("ix_recommendation_outcome_metric_recommendation_type"),
        "recommendation_outcome_metric",
        ["recommendation_type"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_recommendation_outcome_metric_recommendation_type"),
        table_name="recommendation_outcome_metric",
    )
    op.drop_index(op.f("ix_recommendation_outcome_metric_snapshot_id"), table_name="recommendation_outcome_metric")
    op.drop_index("ix_recommendation_outcome_type_created", table_name="recommendation_outcome_metric")
    op.drop_index("ix_recommendation_outcome_snapshot_type", table_name="recommendation_outcome_metric")
    op.drop_table("recommendation_outcome_metric")

    op.drop_index(op.f("ix_workflow_performance_metric_workflow_code"), table_name="workflow_performance_metric")
    op.drop_index(op.f("ix_workflow_performance_metric_workflow_id"), table_name="workflow_performance_metric")
    op.drop_index(op.f("ix_workflow_performance_metric_snapshot_id"), table_name="workflow_performance_metric")
    op.drop_index("ix_workflow_performance_workflow_created", table_name="workflow_performance_metric")
    op.drop_index("ix_workflow_performance_snapshot_workflow", table_name="workflow_performance_metric")
    op.drop_table("workflow_performance_metric")

    op.drop_index(op.f("ix_agent_performance_metric_agent_code"), table_name="agent_performance_metric")
    op.drop_index(op.f("ix_agent_performance_metric_agent_id"), table_name="agent_performance_metric")
    op.drop_index(op.f("ix_agent_performance_metric_snapshot_id"), table_name="agent_performance_metric")
    op.drop_index("ix_agent_performance_agent_created", table_name="agent_performance_metric")
    op.drop_index("ix_agent_performance_snapshot_agent", table_name="agent_performance_metric")
    op.drop_table("agent_performance_metric")

    op.drop_index(op.f("ix_agent_metric_snapshot_generated_at"), table_name="agent_metric_snapshot")
    op.drop_index(op.f("ix_agent_metric_snapshot_snapshot_date"), table_name="agent_metric_snapshot")
    op.drop_index(op.f("ix_agent_metric_snapshot_snapshot_uuid"), table_name="agent_metric_snapshot")
    op.drop_index("ix_agent_metric_snapshot_scope_generated", table_name="agent_metric_snapshot")
    op.drop_index("ix_agent_metric_snapshot_date_generated", table_name="agent_metric_snapshot")
    op.drop_table("agent_metric_snapshot")
