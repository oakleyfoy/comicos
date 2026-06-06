"""add p78 marketplace lifecycle

Revision ID: 20260607_0250
Revises: 20260607_0249
Create Date: 2026-06-07 22:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0250"
down_revision = "20260607_0249"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p78_listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=16), nullable=False),
        sa.Column("sync_state", sa.String(length=16), nullable=False),
        sa.Column("marketplace", sa.String(length=24), nullable=False),
        sa.Column("external_listing_id", sa.String(length=128), nullable=True),
        sa.Column("listing_url", sa.String(length=512), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition_label", sa.String(length=32), nullable=False),
        sa.Column("asking_price", sa.Float(), nullable=False),
        sa.Column("sold_price", sa.Float(), nullable=True),
        sa.Column("quantity_listed", sa.Integer(), nullable=False),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False),
        sa.Column("fees", sa.Float(), nullable=False),
        sa.Column("shipping_cost", sa.Float(), nullable=False),
        sa.Column("export_payload_json", sa.JSON(), nullable=False),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_draft_id"], ["p78_listing_draft.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p78_listing_owner_lifecycle", "p78_listing", ["owner_user_id", "lifecycle_status", "updated_at", "id"])
    op.create_index("ix_p78_listing_owner_draft", "p78_listing", ["owner_user_id", "listing_draft_id", "id"])

    op.create_table(
        "p78_inventory_reservation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["p78_listing.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p78_reservation_owner_listing", "p78_inventory_reservation", ["owner_user_id", "listing_id", "id"])

    op.create_table(
        "p78_sale_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("marketplace", sa.String(length=24), nullable=False),
        sa.Column("sale_price", sa.Float(), nullable=False),
        sa.Column("fees", sa.Float(), nullable=False),
        sa.Column("shipping_cost", sa.Float(), nullable=False),
        sa.Column("cost_basis", sa.Float(), nullable=False),
        sa.Column("profit", sa.Float(), nullable=False),
        sa.Column("roi_pct", sa.Float(), nullable=False),
        sa.Column("quantity_sold", sa.Integer(), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("p73_outcome_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["p78_listing.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["p73_outcome_id"], ["p73_recommendation_outcome.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p78_sale_owner_sold", "p78_sale_record", ["owner_user_id", "sold_at", "id"])

    op.create_table(
        "p78_selling_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p78_sell_analytics_owner_gen", "p78_selling_analytics_snapshot", ["owner_user_id", "generated_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_p78_sell_analytics_owner_gen", table_name="p78_selling_analytics_snapshot")
    op.drop_table("p78_selling_analytics_snapshot")
    op.drop_index("ix_p78_sale_owner_sold", table_name="p78_sale_record")
    op.drop_table("p78_sale_record")
    op.drop_index("ix_p78_reservation_owner_listing", table_name="p78_inventory_reservation")
    op.drop_table("p78_inventory_reservation")
    op.drop_index("ix_p78_listing_owner_draft", table_name="p78_listing")
    op.drop_index("ix_p78_listing_owner_lifecycle", table_name="p78_listing")
    op.drop_table("p78_listing")
