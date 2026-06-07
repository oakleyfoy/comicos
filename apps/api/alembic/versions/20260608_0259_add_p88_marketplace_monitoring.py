"""add p88 marketplace monitoring

Revision ID: 20260608_0259
Revises: 20260608_0258
Create Date: 2026-06-08 07:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0259"
down_revision = "20260608_0258"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p88_marketplace_saved_search",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("variant", sa.String(length=200), nullable=False),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("min_discount_to_fmv", sa.Float(), nullable=True),
        sa.Column("condition_filter", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p88_mkt_saved_search_owner_active",
        "p88_marketplace_saved_search",
        ["owner_user_id", "is_active", "id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_saved_search_owner_user_id"),
        "p88_marketplace_saved_search",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_saved_search_marketplace"),
        "p88_marketplace_saved_search",
        ["marketplace"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_saved_search_is_active"),
        "p88_marketplace_saved_search",
        ["is_active"],
    )

    op.create_table(
        "p88_marketplace_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("saved_search_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["saved_search_id"], ["p88_marketplace_saved_search.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], ["p82_marketplace_acquisition_opportunity.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["p88_marketplace_listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "listing_id",
            "alert_type",
            "dedupe_key",
            name="uq_p88_mkt_alert_dedupe",
        ),
    )
    op.create_index(
        "ix_p88_mkt_alert_owner_status",
        "p88_marketplace_alert",
        ["owner_user_id", "status", "created_at"],
    )

    op.create_table(
        "p88_marketplace_monitoring_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("saved_search_id", sa.Integer(), nullable=True),
        sa.Column("searches_run", sa.Integer(), nullable=False),
        sa.Column("listings_found", sa.Integer(), nullable=False),
        sa.Column("new_listings", sa.Integer(), nullable=False),
        sa.Column("price_drops", sa.Integer(), nullable=False),
        sa.Column("below_fmv_alerts", sa.Integer(), nullable=False),
        sa.Column("watchlist_matches", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["saved_search_id"], ["p88_marketplace_saved_search.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_p88_marketplace_monitoring_run_owner_user_id"),
        "p88_marketplace_monitoring_run",
        ["owner_user_id"],
    )

    op.add_column(
        "p88_marketplace_listing",
        sa.Column("last_price_drop_alert_price", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("p88_marketplace_listing", "last_price_drop_alert_price")
    op.drop_index(
        op.f("ix_p88_marketplace_monitoring_run_owner_user_id"),
        table_name="p88_marketplace_monitoring_run",
    )
    op.drop_table("p88_marketplace_monitoring_run")
    op.drop_index("ix_p88_mkt_alert_owner_status", table_name="p88_marketplace_alert")
    op.drop_table("p88_marketplace_alert")
    op.drop_index(
        op.f("ix_p88_marketplace_saved_search_is_active"),
        table_name="p88_marketplace_saved_search",
    )
    op.drop_index(
        op.f("ix_p88_marketplace_saved_search_marketplace"),
        table_name="p88_marketplace_saved_search",
    )
    op.drop_index(
        op.f("ix_p88_marketplace_saved_search_owner_user_id"),
        table_name="p88_marketplace_saved_search",
    )
    op.drop_index("ix_p88_mkt_saved_search_owner_active", table_name="p88_marketplace_saved_search")
    op.drop_table("p88_marketplace_saved_search")
