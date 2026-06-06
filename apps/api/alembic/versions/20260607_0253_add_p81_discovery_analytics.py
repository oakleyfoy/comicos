"""add p81 discovery analytics

Revision ID: 20260607_0253
Revises: 20260607_0252
Create Date: 2026-06-08 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0253"
down_revision = "20260607_0252"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p81_discovery_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("activity_metrics_json", sa.JSON(), nullable=False),
        sa.Column("conversion_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p81_disc_analytics_owner_date", "p81_discovery_analytics_snapshot", ["owner_user_id", "snapshot_date", "id"])

    op.create_table(
        "p81_discovery_opportunity_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("category_performance_json", sa.JSON(), nullable=False),
        sa.Column("roi_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p81_disc_opp_perf_owner_date", "p81_discovery_opportunity_performance_snapshot", ["owner_user_id", "snapshot_date", "id"]
    )

    op.create_table(
        "p81_discovery_alert_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("engagement_metrics_json", sa.JSON(), nullable=False),
        sa.Column("conversion_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p81_disc_alert_perf_owner_date", "p81_discovery_alert_performance_snapshot", ["owner_user_id", "snapshot_date", "id"]
    )

    op.create_table(
        "p81_discovery_roi_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("fmv_growth_json", sa.JSON(), nullable=False),
        sa.Column("portfolio_roi_pct", sa.Float(), nullable=False),
        sa.Column("performance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p81_disc_roi_owner_date", "p81_discovery_roi_snapshot", ["owner_user_id", "snapshot_date", "id"])


def downgrade() -> None:
    op.drop_index("ix_p81_disc_roi_owner_date", table_name="p81_discovery_roi_snapshot")
    op.drop_table("p81_discovery_roi_snapshot")
    op.drop_index("ix_p81_disc_alert_perf_owner_date", table_name="p81_discovery_alert_performance_snapshot")
    op.drop_table("p81_discovery_alert_performance_snapshot")
    op.drop_index("ix_p81_disc_opp_perf_owner_date", table_name="p81_discovery_opportunity_performance_snapshot")
    op.drop_table("p81_discovery_opportunity_performance_snapshot")
    op.drop_index("ix_p81_disc_analytics_owner_date", table_name="p81_discovery_analytics_snapshot")
    op.drop_table("p81_discovery_analytics_snapshot")
