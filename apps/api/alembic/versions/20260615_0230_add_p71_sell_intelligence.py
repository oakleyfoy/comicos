"""P71 Sell Intelligence Platform

Revision ID: 20260615_0230
Revises: 20260614_0229
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260615_0230"
down_revision = "20260614_0229"
branch_labels = None
depends_on = None


def _snap(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{name}_owner_user_id", name, ["owner_user_id"])


def upgrade() -> None:
    _snap("p71_exit_recommendation_snapshot")
    op.create_index("ix_p71_exit_rec_owner_gen", "p71_exit_recommendation_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p71_exit_recommendation_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("exit_score", sa.Float(), nullable=False),
        sa.Column("exit_confidence", sa.Float(), nullable=False),
        sa.Column("primary_reason", sa.Text(), nullable=False),
        sa.Column("secondary_reasons", sa.JSON(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p71_exit_recommendation_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p71_exit_rec_item_snap", "p71_exit_recommendation_item", ["snapshot_id", "exit_score", "id"])

    _snap("p71_listing_recommendation_snapshot")
    op.create_index("ix_p71_listing_rec_owner_gen", "p71_listing_recommendation_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p71_listing_recommendation_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("suggested_bin", sa.Numeric(12, 2), nullable=True),
        sa.Column("suggested_auction_start", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_sale_low", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_sale_high", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_profit", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_roi_pct", sa.Float(), nullable=False),
        sa.Column("expected_days_to_sell", sa.Float(), nullable=False),
        sa.Column("listing_recommendation", sa.String(length=16), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p71_listing_recommendation_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p71_listing_rec_item_snap", "p71_listing_recommendation_item", ["snapshot_id", "expected_profit", "id"])

    _snap("p71_liquidity_snapshot")
    op.create_index("ix_p71_liquidity_owner_gen", "p71_liquidity_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p71_liquidity_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("liquidity_band", sa.String(length=16), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("sales_velocity", sa.Float(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("demand_strength", sa.Float(), nullable=False),
        sa.Column("market_confidence", sa.Float(), nullable=False),
        sa.Column("days_to_sell_estimate", sa.Float(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p71_liquidity_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p71_liquidity_item_snap", "p71_liquidity_item", ["snapshot_id", "liquidity_score", "id"])

    _snap("p71_exit_queue_snapshot")
    op.create_index("ix_p71_exit_queue_owner_gen", "p71_exit_queue_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p71_exit_queue_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("expected_profit", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_roi_pct", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(length=32), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_days", sa.Float(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p71_exit_queue_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p71_exit_queue_item_snap", "p71_exit_queue_item", ["snapshot_id", "priority", "id"])

    op.create_table(
        "p71_investor_sell_dashboard_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_realized_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("cards_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p71_sell_dash_owner_gen", "p71_investor_sell_dashboard_snapshot", ["owner_user_id", "generated_at", "id"])
    op.create_index("ix_p71_investor_sell_dashboard_snapshot_owner_user_id", "p71_investor_sell_dashboard_snapshot", ["owner_user_id"])


def downgrade() -> None:
    op.drop_table("p71_investor_sell_dashboard_snapshot")
    op.drop_table("p71_exit_queue_item")
    op.drop_table("p71_exit_queue_snapshot")
    op.drop_table("p71_liquidity_item")
    op.drop_table("p71_liquidity_snapshot")
    op.drop_table("p71_listing_recommendation_item")
    op.drop_table("p71_listing_recommendation_snapshot")
    op.drop_table("p71_exit_recommendation_item")
    op.drop_table("p71_exit_recommendation_snapshot")
