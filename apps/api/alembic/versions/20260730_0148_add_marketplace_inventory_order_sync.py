"""add marketplace inventory order sync

Revision ID: 20260730_0148
Revises: 20260729_0147
Create Date: 2026-07-30 01:48:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260730_0148"
down_revision = "20260729_0147"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_inventory_reservation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("reservation_uuid", sa.String(length=64), nullable=False),
        sa.Column("reservation_type", sa.String(length=40), nullable=False),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_uuid", name="uq_marketplace_inventory_reservation_uuid"),
    )
    op.create_index("ix_marketplace_inventory_reservation_owner_id", "marketplace_inventory_reservation", ["owner_id"])
    op.create_index("ix_marketplace_inventory_reservation_listing_id", "marketplace_inventory_reservation", ["listing_id"])
    op.create_index(
        "ix_marketplace_inventory_reservation_inventory_copy_id",
        "marketplace_inventory_reservation",
        ["inventory_copy_id"],
    )
    op.create_index(
        "ix_marketplace_inventory_reservation_reservation_uuid",
        "marketplace_inventory_reservation",
        ["reservation_uuid"],
    )
    op.create_index("ix_marketplace_inventory_reservation_status", "marketplace_inventory_reservation", ["status"])
    op.create_index("ix_marketplace_inventory_reservation_created_at", "marketplace_inventory_reservation", ["created_at"])

    op.create_table(
        "marketplace_inventory_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("sold_quantity", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_inventory_availability_owner_id", "marketplace_inventory_availability", ["owner_id"])
    op.create_index("ix_marketplace_inventory_availability_listing_id", "marketplace_inventory_availability", ["listing_id"])
    op.create_index(
        "ix_marketplace_inventory_availability_inventory_copy_id",
        "marketplace_inventory_availability",
        ["inventory_copy_id"],
    )
    op.create_index(
        "ix_marketplace_inventory_availability_calculated_at",
        "marketplace_inventory_availability",
        ["calculated_at"],
    )

    op.create_table(
        "marketplace_order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("order_uuid", sa.String(length=64), nullable=False),
        sa.Column("external_order_id", sa.String(length=200), nullable=True),
        sa.Column("order_status", sa.String(length=24), nullable=False),
        sa.Column("buyer_name", sa.String(length=200), nullable=True),
        sa.Column("buyer_email", sa.String(length=320), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_uuid", name="uq_marketplace_order_uuid"),
    )
    op.create_index("ix_marketplace_order_owner_id", "marketplace_order", ["owner_id"])
    op.create_index("ix_marketplace_order_marketplace_id", "marketplace_order", ["marketplace_id"])
    op.create_index("ix_marketplace_order_marketplace_account_id", "marketplace_order", ["marketplace_account_id"])
    op.create_index("ix_marketplace_order_order_uuid", "marketplace_order", ["order_uuid"])
    op.create_index("ix_marketplace_order_external_order_id", "marketplace_order", ["external_order_id"])
    op.create_index("ix_marketplace_order_order_status", "marketplace_order", ["order_status"])
    op.create_index("ix_marketplace_order_created_at", "marketplace_order", ["created_at"])

    op.create_table(
        "marketplace_order_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("external_item_id", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("item_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["marketplace_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_order_item_order_id", "marketplace_order_item", ["order_id"])
    op.create_index("ix_marketplace_order_item_listing_id", "marketplace_order_item", ["listing_id"])
    op.create_index("ix_marketplace_order_item_inventory_copy_id", "marketplace_order_item", ["inventory_copy_id"])
    op.create_index("ix_marketplace_order_item_created_at", "marketplace_order_item", ["created_at"])

    op.create_table(
        "marketplace_order_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["marketplace_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_order_event_order_id", "marketplace_order_event", ["order_id"])
    op.create_index("ix_marketplace_order_event_created_at", "marketplace_order_event", ["created_at"])

    op.create_table(
        "marketplace_inventory_sync_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("plan_uuid", sa.String(length=64), nullable=False),
        sa.Column("plan_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_uuid", name="uq_marketplace_inventory_sync_plan_uuid"),
    )
    op.create_index("ix_marketplace_inventory_sync_plan_owner_id", "marketplace_inventory_sync_plan", ["owner_id"])
    op.create_index("ix_marketplace_inventory_sync_plan_plan_uuid", "marketplace_inventory_sync_plan", ["plan_uuid"])
    op.create_index("ix_marketplace_inventory_sync_plan_status", "marketplace_inventory_sync_plan", ["status"])
    op.create_index("ix_marketplace_inventory_sync_plan_created_at", "marketplace_inventory_sync_plan", ["created_at"])

    op.create_table(
        "marketplace_inventory_sync_plan_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("current_available_quantity", sa.Integer(), nullable=False),
        sa.Column("target_available_quantity", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["marketplace_inventory_sync_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_inventory_sync_plan_item_plan_id", "marketplace_inventory_sync_plan_item", ["plan_id"])
    op.create_index("ix_marketplace_inventory_sync_plan_item_listing_id", "marketplace_inventory_sync_plan_item", ["listing_id"])
    op.create_index(
        "ix_marketplace_inventory_sync_plan_item_marketplace_id",
        "marketplace_inventory_sync_plan_item",
        ["marketplace_id"],
    )
    op.create_index(
        "ix_marketplace_inventory_sync_plan_item_marketplace_account_id",
        "marketplace_inventory_sync_plan_item",
        ["marketplace_account_id"],
    )
    op.create_index("ix_marketplace_inventory_sync_plan_item_created_at", "marketplace_inventory_sync_plan_item", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_inventory_sync_plan_item_created_at", table_name="marketplace_inventory_sync_plan_item")
    op.drop_index(
        "ix_marketplace_inventory_sync_plan_item_marketplace_account_id",
        table_name="marketplace_inventory_sync_plan_item",
    )
    op.drop_index("ix_marketplace_inventory_sync_plan_item_marketplace_id", table_name="marketplace_inventory_sync_plan_item")
    op.drop_index("ix_marketplace_inventory_sync_plan_item_listing_id", table_name="marketplace_inventory_sync_plan_item")
    op.drop_index("ix_marketplace_inventory_sync_plan_item_plan_id", table_name="marketplace_inventory_sync_plan_item")
    op.drop_table("marketplace_inventory_sync_plan_item")

    op.drop_index("ix_marketplace_inventory_sync_plan_created_at", table_name="marketplace_inventory_sync_plan")
    op.drop_index("ix_marketplace_inventory_sync_plan_status", table_name="marketplace_inventory_sync_plan")
    op.drop_index("ix_marketplace_inventory_sync_plan_plan_uuid", table_name="marketplace_inventory_sync_plan")
    op.drop_index("ix_marketplace_inventory_sync_plan_owner_id", table_name="marketplace_inventory_sync_plan")
    op.drop_table("marketplace_inventory_sync_plan")

    op.drop_index("ix_marketplace_order_event_created_at", table_name="marketplace_order_event")
    op.drop_index("ix_marketplace_order_event_order_id", table_name="marketplace_order_event")
    op.drop_table("marketplace_order_event")

    op.drop_index("ix_marketplace_order_item_created_at", table_name="marketplace_order_item")
    op.drop_index("ix_marketplace_order_item_inventory_copy_id", table_name="marketplace_order_item")
    op.drop_index("ix_marketplace_order_item_listing_id", table_name="marketplace_order_item")
    op.drop_index("ix_marketplace_order_item_order_id", table_name="marketplace_order_item")
    op.drop_table("marketplace_order_item")

    op.drop_index("ix_marketplace_order_created_at", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_order_status", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_external_order_id", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_order_uuid", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_marketplace_account_id", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_marketplace_id", table_name="marketplace_order")
    op.drop_index("ix_marketplace_order_owner_id", table_name="marketplace_order")
    op.drop_table("marketplace_order")

    op.drop_index("ix_marketplace_inventory_availability_calculated_at", table_name="marketplace_inventory_availability")
    op.drop_index(
        "ix_marketplace_inventory_availability_inventory_copy_id",
        table_name="marketplace_inventory_availability",
    )
    op.drop_index("ix_marketplace_inventory_availability_listing_id", table_name="marketplace_inventory_availability")
    op.drop_index("ix_marketplace_inventory_availability_owner_id", table_name="marketplace_inventory_availability")
    op.drop_table("marketplace_inventory_availability")

    op.drop_index("ix_marketplace_inventory_reservation_created_at", table_name="marketplace_inventory_reservation")
    op.drop_index("ix_marketplace_inventory_reservation_status", table_name="marketplace_inventory_reservation")
    op.drop_index(
        "ix_marketplace_inventory_reservation_reservation_uuid",
        table_name="marketplace_inventory_reservation",
    )
    op.drop_index(
        "ix_marketplace_inventory_reservation_inventory_copy_id",
        table_name="marketplace_inventory_reservation",
    )
    op.drop_index("ix_marketplace_inventory_reservation_listing_id", table_name="marketplace_inventory_reservation")
    op.drop_index("ix_marketplace_inventory_reservation_owner_id", table_name="marketplace_inventory_reservation")
    op.drop_table("marketplace_inventory_reservation")
