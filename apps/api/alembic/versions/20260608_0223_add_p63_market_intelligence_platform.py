"""add P63 market intelligence platform tables

Revision ID: 20260608_0223
Revises: 20260607_0222
Create Date: 2026-06-08 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0223"
down_revision = "20260607_0222"
branch_labels = None
depends_on = None


def _snapshot_cols() -> list:
    return [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "portfolio_performance_snapshot",
        *_snapshot_cols(),
        sa.Column("total_cost_basis", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_current_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_unrealized_gain", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_unrealized_gain_pct", sa.Float(), nullable=False),
        sa.Column("top_gainers_count", sa.Integer(), nullable=False),
        sa.Column("top_losers_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_perf_snap_owner_gen", "portfolio_performance_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "portfolio_performance_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain_pct", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("performance_tier", sa.String(length=24), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_performance_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_perf_item_snap_gain", "portfolio_performance_item", ["snapshot_id", "unrealized_gain_pct", "id"])

    op.create_table(
        "sell_signal_snapshot",
        *_snapshot_cols(),
        sa.Column("strong_sell_count", sa.Integer(), nullable=False),
        sa.Column("consider_sell_count", sa.Integer(), nullable=False),
        sa.Column("hold_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sell_signal_snap_owner_gen", "sell_signal_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "sell_signal_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("sell_score", sa.Float(), nullable=False),
        sa.Column("hold_score", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain_pct", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("quantity_owned", sa.Integer(), nullable=False),
        sa.Column("grade_status", sa.String(length=32), nullable=False),
        sa.Column("sell_reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["sell_signal_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sell_signal_item_snap_score", "sell_signal_item", ["snapshot_id", "sell_score", "id"])

    op.create_table(
        "acquisition_opportunity_snapshot",
        *_snapshot_cols(),
        sa.Column("high_priority_count", sa.Integer(), nullable=False),
        sa.Column("watch_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_acq_opp_snap_owner_gen", "acquisition_opportunity_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "acquisition_opportunity_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("spec_score", sa.Float(), nullable=False),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("estimated_market_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_buy_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["acquisition_opportunity_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_acq_opp_item_snap_score", "acquisition_opportunity_item", ["snapshot_id", "opportunity_score", "id"])

    op.create_table(
        "market_signal_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_signal_snap_scope_gen", "market_signal_snapshot", ["scope", "owner_user_id", "generated_at", "id"])

    op.create_table(
        "market_signal_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("market_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("price_score", sa.Float(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("signal_reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["market_signal_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_signal_item_snap_score", "market_signal_item", ["snapshot_id", "market_score", "id"])


def downgrade() -> None:
    for table in (
        "market_signal_item",
        "market_signal_snapshot",
        "acquisition_opportunity_item",
        "acquisition_opportunity_snapshot",
        "sell_signal_item",
        "sell_signal_snapshot",
        "portfolio_performance_item",
        "portfolio_performance_snapshot",
    ):
        op.drop_table(table)
