"""P68 Market Pricing Engine

Revision ID: 20260614_0229
Revises: 20260613_0228
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260614_0229"
down_revision = "20260613_0228"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p68_market_pricing_provider",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("last_ingest_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p68_mkt_provider_owner", "p68_market_pricing_provider", ["owner_user_id", "provider_type", "id"])

    op.create_table(
        "p68_market_price_observation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("external_listing_id", sa.String(length=128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("series_key", sa.String(length=255), nullable=True),
        sa.Column("variant_label", sa.String(length=255), nullable=True),
        sa.Column("printing_number", sa.Integer(), nullable=True),
        sa.Column("printing_kind", sa.String(length=32), nullable=True),
        sa.Column("grade", sa.String(length=32), nullable=True),
        sa.Column("raw_or_graded", sa.String(length=16), nullable=False),
        sa.Column("sold_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p68_mkt_obs_owner_obs", "p68_market_price_observation", ["owner_user_id", "observed_at", "id"])

    op.create_table(
        "p68_market_price_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("variant_label", sa.String(length=255), nullable=True),
        sa.Column("printing_number", sa.Integer(), nullable=True),
        sa.Column("printing_kind", sa.String(length=32), nullable=True),
        sa.Column("raw_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("graded_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("blended_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("low_sale", sa.Numeric(12, 2), nullable=True),
        sa.Column("high_sale", sa.Numeric(12, 2), nullable=True),
        sa.Column("median_sale", sa.Numeric(12, 2), nullable=True),
        sa.Column("average_sale", sa.Numeric(12, 2), nullable=True),
        sa.Column("sales_count", sa.Integer(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("price_trend_30d", sa.String(length=16), nullable=False),
        sa.Column("price_trend_90d", sa.String(length=16), nullable=False),
        sa.Column("primary_provider", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p68_mkt_snap_owner_gen", "p68_market_price_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p68_market_price_match_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("observation_id", sa.Integer(), nullable=False),
        sa.Column("target_inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("matched_reason", sa.Text(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("identity_warnings", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["observation_id"], ["p68_market_price_observation.id"]),
        sa.ForeignKeyConstraint(["target_inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p68_mkt_match_obs", "p68_market_price_match_result", ["observation_id", "id"])

    op.create_table(
        "p68_inventory_computed_fmv",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("computed_fmv", sa.Numeric(12, 2), nullable=False),
        sa.Column("computed_fmv_source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provider_blend_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p68_market_price_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p68_inv_computed_fmv_owner", "p68_inventory_computed_fmv", ["owner_user_id", "inventory_copy_id", "id"])


def downgrade() -> None:
    for t in (
        "p68_inventory_computed_fmv",
        "p68_market_price_match_result",
        "p68_market_price_snapshot",
        "p68_market_price_observation",
        "p68_market_pricing_provider",
    ):
        op.drop_table(t)
