"""add P73-02 recommendation performance analytics

Revision ID: 20260607_0237
Revises: 20260607_0236
Create Date: 2026-06-07 02:37:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0237"
down_revision = "20260607_0236"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("publisher", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("character", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("creator", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("expected_profit", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("actual_profit", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("expected_roi_pct", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "p73_recommendation_outcome",
        sa.Column("actual_roi_pct", sa.Numeric(12, 2), nullable=True),
    )

    op.create_table(
        "p73_recommendation_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recommendations_generated", sa.Integer(), nullable=False),
        sa.Column("viewed", sa.Integer(), nullable=False),
        sa.Column("purchased", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("held", sa.Integer(), nullable=False),
        sa.Column("graded", sa.Integer(), nullable=False),
        sa.Column("sold", sa.Integer(), nullable=False),
        sa.Column("view_rate_pct", sa.Float(), nullable=False),
        sa.Column("purchase_rate_pct", sa.Float(), nullable=False),
        sa.Column("watchlist_rate_pct", sa.Float(), nullable=False),
        sa.Column("grade_rate_pct", sa.Float(), nullable=False),
        sa.Column("sell_rate_pct", sa.Float(), nullable=False),
        sa.Column("success_rate_pct", sa.Float(), nullable=False),
        sa.Column("failure_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_return_pct", sa.Float(), nullable=False),
        sa.Column("median_return_pct", sa.Float(), nullable=False),
        sa.Column("win_rate_pct", sa.Float(), nullable=False),
        sa.Column("loss_rate_pct", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_perf_snap_owner_gen",
        "p73_recommendation_performance_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )
    op.create_index(
        op.f("ix_p73_recommendation_performance_snapshot_owner_user_id"),
        "p73_recommendation_performance_snapshot",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_p73_recommendation_performance_snapshot_snapshot_date"),
        "p73_recommendation_performance_snapshot",
        ["snapshot_date"],
    )

    op.create_table(
        "p73_recommendation_profitability_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("performance_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("expected_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_roi_pct", sa.Float(), nullable=False),
        sa.Column("actual_roi_pct", sa.Float(), nullable=False),
        sa.Column("breakdown_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["performance_snapshot_id"], ["p73_recommendation_performance_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_profit_snap_owner",
        "p73_recommendation_profitability_snapshot",
        ["owner_user_id", "performance_snapshot_id", "id"],
    )

    op.create_table(
        "p73_recommendation_category_performance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("performance_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=32), nullable=False),
        sa.Column("recommendation_count", sa.Integer(), nullable=False),
        sa.Column("success_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_roi_pct", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["performance_snapshot_id"], ["p73_recommendation_performance_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_cat_perf_snap",
        "p73_recommendation_category_performance",
        ["performance_snapshot_id", "recommendation_type", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p73_rec_cat_perf_snap", table_name="p73_recommendation_category_performance")
    op.drop_table("p73_recommendation_category_performance")
    op.drop_index("ix_p73_rec_profit_snap_owner", table_name="p73_recommendation_profitability_snapshot")
    op.drop_table("p73_recommendation_profitability_snapshot")
    op.drop_index(
        op.f("ix_p73_recommendation_performance_snapshot_snapshot_date"),
        table_name="p73_recommendation_performance_snapshot",
    )
    op.drop_index(
        op.f("ix_p73_recommendation_performance_snapshot_owner_user_id"),
        table_name="p73_recommendation_performance_snapshot",
    )
    op.drop_index("ix_p73_rec_perf_snap_owner_gen", table_name="p73_recommendation_performance_snapshot")
    op.drop_table("p73_recommendation_performance_snapshot")
    op.drop_column("p73_recommendation_outcome", "actual_roi_pct")
    op.drop_column("p73_recommendation_outcome", "expected_roi_pct")
    op.drop_column("p73_recommendation_outcome", "actual_profit")
    op.drop_column("p73_recommendation_outcome", "expected_profit")
    op.drop_column("p73_recommendation_outcome", "creator")
    op.drop_column("p73_recommendation_outcome", "character")
    op.drop_column("p73_recommendation_outcome", "publisher")
