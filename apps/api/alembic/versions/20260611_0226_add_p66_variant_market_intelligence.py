"""add P66 variant and market intelligence tables

Revision ID: 20260611_0226
Revises: 20260610_0225
Create Date: 2026-06-11 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260611_0226"
down_revision = "20260610_0225"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "variant_intelligence_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_variant_intel_snap_owner_gen", "variant_intelligence_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "variant_intelligence_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_variant_id", sa.Integer(), nullable=True),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("cover_label", sa.String(length=64), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=False),
        sa.Column("variant_score", sa.Float(), nullable=False),
        sa.Column("variant_tier", sa.String(length=2), nullable=False),
        sa.Column("variant_reason", sa.Text(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["external_catalog_variant_id"], ["external_catalog_variant.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["variant_intelligence_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_variant_intel_item_snap_score", "variant_intelligence_item", ["snapshot_id", "variant_score", "id"])

    op.create_table(
        "quantity_recommendation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quantity_rec_snap_owner_gen", "quantity_recommendation_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "quantity_recommendation_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("buy_queue_item_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("collection_quantity", sa.Integer(), nullable=False),
        sa.Column("spec_quantity", sa.Integer(), nullable=False),
        sa.Column("flip_quantity", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["quantity_recommendation_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quantity_rec_item_snap", "quantity_recommendation_item", ["snapshot_id", "buy_queue_item_id", "id"])

    op.create_table(
        "market_price_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("total_observations", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_price_snap_owner_gen", "market_price_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "market_price_observation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_variant_id", sa.Integer(), nullable=True),
        sa.Column("fmv", sa.Float(), nullable=False),
        sa.Column("price_trend", sa.String(length=16), nullable=False),
        sa.Column("liquidity", sa.String(length=16), nullable=False),
        sa.Column("market_confidence", sa.Float(), nullable=False),
        sa.Column("source_key", sa.String(length=32), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["external_catalog_variant_id"], ["external_catalog_variant.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["market_price_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_price_obs_snap", "market_price_observation", ["snapshot_id", "external_catalog_variant_id", "id"])

    op.create_table(
        "variant_decision_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_issues", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_variant_decision_snap_owner_gen", "variant_decision_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "variant_decision_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("buy_queue_item_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("recommendation_summary", sa.Text(), nullable=False),
        sa.Column("cover_ranking_json", sa.JSON(), nullable=False),
        sa.Column("buy_plan_json", sa.JSON(), nullable=False),
        sa.Column("skip_covers_json", sa.JSON(), nullable=False),
        sa.Column("quantity_plan_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["variant_decision_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_variant_decision_item_snap", "variant_decision_item", ["snapshot_id", "external_catalog_issue_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_variant_decision_item_snap", table_name="variant_decision_item")
    op.drop_table("variant_decision_item")
    op.drop_index("ix_variant_decision_snap_owner_gen", table_name="variant_decision_snapshot")
    op.drop_table("variant_decision_snapshot")
    op.drop_index("ix_market_price_obs_snap", table_name="market_price_observation")
    op.drop_table("market_price_observation")
    op.drop_index("ix_market_price_snap_owner_gen", table_name="market_price_snapshot")
    op.drop_table("market_price_snapshot")
    op.drop_index("ix_quantity_rec_item_snap", table_name="quantity_recommendation_item")
    op.drop_table("quantity_recommendation_item")
    op.drop_index("ix_quantity_rec_snap_owner_gen", table_name="quantity_recommendation_snapshot")
    op.drop_table("quantity_recommendation_snapshot")
    op.drop_index("ix_variant_intel_item_snap_score", table_name="variant_intelligence_item")
    op.drop_table("variant_intelligence_item")
    op.drop_index("ix_variant_intel_snap_owner_gen", table_name="variant_intelligence_snapshot")
    op.drop_table("variant_intelligence_snapshot")
