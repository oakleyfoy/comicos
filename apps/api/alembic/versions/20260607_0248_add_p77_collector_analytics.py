"""add p77 collector analytics snapshots

Revision ID: 20260607_0248
Revises: 20260607_0247
Create Date: 2026-06-07 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0248"
down_revision = "20260607_0247"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p77_collector_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profile_metrics_json", sa.JSON(), nullable=False),
        sa.Column("goal_metrics_json", sa.JSON(), nullable=False),
        sa.Column("personalization_metrics_json", sa.JSON(), nullable=False),
        sa.Column("assistant_metrics_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p77_analytics_snap_owner_gen", "p77_collector_analytics_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p77_recommendation_adjustment_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recommendations_evaluated", sa.Integer(), nullable=False),
        sa.Column("recommendations_adjusted", sa.Integer(), nullable=False),
        sa.Column("adjustment_rate_pct", sa.Float(), nullable=False),
        sa.Column("category_breakdown_json", sa.JSON(), nullable=False),
        sa.Column("sample_adjustments_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p77_adj_snap_owner_gen", "p77_recommendation_adjustment_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p77_budget_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monthly_budget", sa.Float(), nullable=False),
        sa.Column("monthly_spend", sa.Float(), nullable=False),
        sa.Column("utilization_percent", sa.Float(), nullable=False),
        sa.Column("budget_state", sa.String(length=8), nullable=False),
        sa.Column("category_spend_json", sa.JSON(), nullable=False),
        sa.Column("forecast_json", sa.JSON(), nullable=False),
        sa.Column("compliance_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p77_budget_snap_owner_gen", "p77_budget_performance_snapshot", ["owner_user_id", "generated_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_p77_budget_snap_owner_gen", table_name="p77_budget_performance_snapshot")
    op.drop_table("p77_budget_performance_snapshot")
    op.drop_index("ix_p77_adj_snap_owner_gen", table_name="p77_recommendation_adjustment_snapshot")
    op.drop_table("p77_recommendation_adjustment_snapshot")
    op.drop_index("ix_p77_analytics_snap_owner_gen", table_name="p77_collector_analytics_snapshot")
    op.drop_table("p77_collector_analytics_snapshot")
