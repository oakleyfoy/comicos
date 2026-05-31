"""add marketplace catalog listing model

Revision ID: 20260728_0146
Revises: 20260727_0145
Create Date: 2026-07-28 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260728_0146"
down_revision = "20260727_0145"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("listing_uuid", sa.String(length=64), nullable=False),
        sa.Column("listing_title", sa.String(length=500), nullable=False),
        sa.Column("listing_description", sa.String(), nullable=True),
        sa.Column("listing_type", sa.String(length=80), nullable=False),
        sa.Column("condition_label", sa.String(length=120), nullable=False),
        sa.Column("grade_label", sa.String(length=120), nullable=True),
        sa.Column("asking_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_uuid", name="uq_marketplace_listing_uuid"),
    )
    op.create_index("ix_marketplace_listing_listing_uuid", "marketplace_listing", ["listing_uuid"])
    op.create_index("ix_marketplace_listing_created_at", "marketplace_listing", ["created_at"])
    op.create_index(op.f("ix_marketplace_listing_owner_id"), "marketplace_listing", ["owner_id"])
    op.create_index(op.f("ix_marketplace_listing_inventory_copy_id"), "marketplace_listing", ["inventory_copy_id"])
    op.create_index(op.f("ix_marketplace_listing_status"), "marketplace_listing", ["status"])

    op.create_table(
        "marketplace_listing_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("variant_code", sa.String(length=80), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=120), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "variant_code", name="uq_marketplace_listing_variant_code"),
    )
    op.create_index(op.f("ix_marketplace_listing_variant_listing_id"), "marketplace_listing_variant", ["listing_id"])

    op.create_table(
        "marketplace_listing_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("image_type", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "sort_order", name="uq_marketplace_listing_image_sort_order"),
    )
    op.create_index(op.f("ix_marketplace_listing_image_listing_id"), "marketplace_listing_image", ["listing_id"])

    op.create_table(
        "marketplace_listing_price",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("price_type", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketplace_listing_price_listing_id"), "marketplace_listing_price", ["listing_id"])

    op.create_table(
        "marketplace_listing_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marketplace_listing_status_history_listing_id"), "marketplace_listing_status_history", ["listing_id"])

    op.create_table(
        "marketplace_listing_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("external_listing_id", sa.String(length=200), nullable=True),
        sa.Column("external_url", sa.String(), nullable=True),
        sa.Column("sync_status", sa.String(length=24), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_listing_mapping_created_at", "marketplace_listing_mapping", ["created_at"])
    op.create_index(op.f("ix_marketplace_listing_mapping_listing_id"), "marketplace_listing_mapping", ["listing_id"])
    op.create_index(op.f("ix_marketplace_listing_mapping_marketplace_id"), "marketplace_listing_mapping", ["marketplace_id"])
    op.create_index(op.f("ix_marketplace_listing_mapping_marketplace_account_id"), "marketplace_listing_mapping", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_listing_mapping_external_listing_id"), "marketplace_listing_mapping", ["external_listing_id"])
    op.create_index(op.f("ix_marketplace_listing_mapping_sync_status"), "marketplace_listing_mapping", ["sync_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_listing_mapping_sync_status"), table_name="marketplace_listing_mapping")
    op.drop_index(op.f("ix_marketplace_listing_mapping_external_listing_id"), table_name="marketplace_listing_mapping")
    op.drop_index(op.f("ix_marketplace_listing_mapping_marketplace_account_id"), table_name="marketplace_listing_mapping")
    op.drop_index(op.f("ix_marketplace_listing_mapping_marketplace_id"), table_name="marketplace_listing_mapping")
    op.drop_index(op.f("ix_marketplace_listing_mapping_listing_id"), table_name="marketplace_listing_mapping")
    op.drop_index("ix_marketplace_listing_mapping_created_at", table_name="marketplace_listing_mapping")
    op.drop_table("marketplace_listing_mapping")

    op.drop_index(op.f("ix_marketplace_listing_status_history_listing_id"), table_name="marketplace_listing_status_history")
    op.drop_table("marketplace_listing_status_history")

    op.drop_index(op.f("ix_marketplace_listing_price_listing_id"), table_name="marketplace_listing_price")
    op.drop_table("marketplace_listing_price")

    op.drop_index(op.f("ix_marketplace_listing_image_listing_id"), table_name="marketplace_listing_image")
    op.drop_table("marketplace_listing_image")

    op.drop_index(op.f("ix_marketplace_listing_variant_listing_id"), table_name="marketplace_listing_variant")
    op.drop_table("marketplace_listing_variant")

    op.drop_index(op.f("ix_marketplace_listing_status"), table_name="marketplace_listing")
    op.drop_index(op.f("ix_marketplace_listing_inventory_copy_id"), table_name="marketplace_listing")
    op.drop_index(op.f("ix_marketplace_listing_owner_id"), table_name="marketplace_listing")
    op.drop_index("ix_marketplace_listing_created_at", table_name="marketplace_listing")
    op.drop_index("ix_marketplace_listing_listing_uuid", table_name="marketplace_listing")
    op.drop_table("marketplace_listing")
