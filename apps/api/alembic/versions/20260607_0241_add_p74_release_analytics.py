"""add P74-03 release analytics

Revision ID: 20260607_0241
Revises: 20260607_0240
Create Date: 2026-06-07 02:41:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0241"
down_revision = "20260607_0240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p74_release_outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("recommended_quantity", sa.Integer(), nullable=False),
        sa.Column("ordered_quantity", sa.Integer(), nullable=False),
        sa.Column("actual_quantity_purchased", sa.Integer(), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("market_performance_pct", sa.Float(), nullable=False),
        sa.Column("inventory_performance_pct", sa.Float(), nullable=False),
        sa.Column("actual_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_roi_pct", sa.Float(), nullable=False),
        sa.Column("outcome_status", sa.String(length=24), nullable=False),
        sa.Column("purchase_action", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_release_outcome_owner_issue",
        "p74_release_outcome",
        ["owner_user_id", "release_issue_id", "id"],
    )

    op.create_table(
        "p74_release_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcomes_tracked", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("platform_confidence_pct", sa.Float(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_rel_analytics_owner",
        "p74_release_analytics_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )

    op.create_table(
        "p74_foc_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("accuracy_rate_pct", sa.Float(), nullable=False),
        sa.Column("upgrade_accuracy_pct", sa.Float(), nullable=False),
        sa.Column("downgrade_accuracy_pct", sa.Float(), nullable=False),
        sa.Column("missed_opportunity_rate_pct", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p74_release_analytics_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_foc_perf_owner",
        "p74_foc_performance_snapshot",
        ["owner_user_id", "analytics_snapshot_id", "id"],
    )

    op.create_table(
        "p74_quantity_recommendation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("success_rate_pct", sa.Float(), nullable=False),
        sa.Column("failure_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_roi_pct", sa.Float(), nullable=False),
        sa.Column("median_roi_pct", sa.Float(), nullable=False),
        sa.Column("by_action_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p74_release_analytics_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_qty_rec_owner",
        "p74_quantity_recommendation_snapshot",
        ["owner_user_id", "analytics_snapshot_id", "id"],
    )

    op.create_table(
        "p74_release_category_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("category_key", sa.String(length=48), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("success_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_roi_pct", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p74_release_analytics_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_rel_cat_snap",
        "p74_release_category_snapshot",
        ["analytics_snapshot_id", "category_key", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p74_rel_cat_snap", table_name="p74_release_category_snapshot")
    op.drop_table("p74_release_category_snapshot")
    op.drop_index("ix_p74_qty_rec_owner", table_name="p74_quantity_recommendation_snapshot")
    op.drop_table("p74_quantity_recommendation_snapshot")
    op.drop_index("ix_p74_foc_perf_owner", table_name="p74_foc_performance_snapshot")
    op.drop_table("p74_foc_performance_snapshot")
    op.drop_index("ix_p74_rel_analytics_owner", table_name="p74_release_analytics_snapshot")
    op.drop_table("p74_release_analytics_snapshot")
    op.drop_index("ix_p74_release_outcome_owner_issue", table_name="p74_release_outcome")
    op.drop_table("p74_release_outcome")
