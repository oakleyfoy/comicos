"""add p88 marketplace listings and search runs

Revision ID: 20260608_0258
Revises: 20260608_0257
Create Date: 2026-06-08 06:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0258"
down_revision = "20260608_0257"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p88_marketplace_listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("listing_url", sa.String(length=2048), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("previous_price", sa.Float(), nullable=True),
        sa.Column("shipping_cost", sa.Float(), nullable=False),
        sa.Column("condition", sa.String(length=128), nullable=False),
        sa.Column("seller_name", sa.String(length=128), nullable=False),
        sa.Column("listing_type", sa.String(length=64), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], ["p82_marketplace_acquisition_opportunity.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "marketplace", "item_id", name="uq_p88_mkt_listing_item"),
    )
    op.create_index("ix_p88_mkt_listing_opp", "p88_marketplace_listing", ["opportunity_id", "is_active"])
    op.create_index(
        op.f("ix_p88_marketplace_listing_owner_user_id"),
        "p88_marketplace_listing",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_listing_marketplace"),
        "p88_marketplace_listing",
        ["marketplace"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_listing_item_id"),
        "p88_marketplace_listing",
        ["item_id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_listing_is_active"),
        "p88_marketplace_listing",
        ["is_active"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_listing_health_status"),
        "p88_marketplace_listing",
        ["health_status"],
    )

    op.create_table(
        "p88_marketplace_search_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("searches_run", sa.Integer(), nullable=False),
        sa.Column("listings_found", sa.Integer(), nullable=False),
        sa.Column("new_listings", sa.Integer(), nullable=False),
        sa.Column("updated_listings", sa.Integer(), nullable=False),
        sa.Column("failed_searches", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_p88_marketplace_search_run_owner_user_id"),
        "p88_marketplace_search_run",
        ["owner_user_id"],
    )

    op.add_column(
        "p82_marketplace_acquisition_opportunity",
        sa.Column("best_listing_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_p82_mkt_acq_best_listing",
        "p82_marketplace_acquisition_opportunity",
        "p88_marketplace_listing",
        ["best_listing_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_p82_marketplace_acquisition_opportunity_best_listing_id"),
        "p82_marketplace_acquisition_opportunity",
        ["best_listing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_p82_marketplace_acquisition_opportunity_best_listing_id"),
        table_name="p82_marketplace_acquisition_opportunity",
    )
    op.drop_constraint("fk_p82_mkt_acq_best_listing", "p82_marketplace_acquisition_opportunity", type_="foreignkey")
    op.drop_column("p82_marketplace_acquisition_opportunity", "best_listing_id")

    op.drop_index(
        op.f("ix_p88_marketplace_search_run_owner_user_id"),
        table_name="p88_marketplace_search_run",
    )
    op.drop_table("p88_marketplace_search_run")

    op.drop_index(op.f("ix_p88_marketplace_listing_health_status"), table_name="p88_marketplace_listing")
    op.drop_index(op.f("ix_p88_marketplace_listing_is_active"), table_name="p88_marketplace_listing")
    op.drop_index(op.f("ix_p88_marketplace_listing_item_id"), table_name="p88_marketplace_listing")
    op.drop_index(op.f("ix_p88_marketplace_listing_marketplace"), table_name="p88_marketplace_listing")
    op.drop_index(op.f("ix_p88_marketplace_listing_owner_user_id"), table_name="p88_marketplace_listing")
    op.drop_index("ix_p88_mkt_listing_opp", table_name="p88_marketplace_listing")
    op.drop_table("p88_marketplace_listing")
