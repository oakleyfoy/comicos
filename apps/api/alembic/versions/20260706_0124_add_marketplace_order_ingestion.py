"""add marketplace order ingestion foundation

Revision ID: 20260706_0124
Revises: 20260705_0123
Create Date: 2026-07-06 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260706_0124"
down_revision = "20260705_0123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_order_identifier", sa.String(length=255), nullable=False),
        sa.Column("marketplace_type", sa.String(length=32), nullable=False),
        sa.Column("order_status", sa.String(length=24), nullable=False),
        sa.Column("buyer_identifier", sa.String(length=255), nullable=True),
        sa.Column("order_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("order_currency", sa.String(length=8), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "marketplace_account_id",
            "marketplace_order_identifier",
            name="uq_marketplace_order_identity",
        ),
    )
    op.create_index("ix_mkt_order_org_ordered", "marketplace_orders", ["organization_id", "ordered_at", "id"])
    op.create_index(
        "ix_mkt_order_org_account_ordered",
        "marketplace_orders",
        ["organization_id", "marketplace_account_id", "ordered_at", "id"],
    )
    op.create_index(
        "ix_mkt_order_org_status_ordered",
        "marketplace_orders",
        ["organization_id", "order_status", "ordered_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_orders_buyer_identifier"), "marketplace_orders", ["buyer_identifier"])
    op.create_index(op.f("ix_marketplace_orders_marketplace_account_id"), "marketplace_orders", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_orders_marketplace_order_identifier"), "marketplace_orders", ["marketplace_order_identifier"])
    op.create_index(op.f("ix_marketplace_orders_marketplace_type"), "marketplace_orders", ["marketplace_type"])
    op.create_index(op.f("ix_marketplace_orders_order_status"), "marketplace_orders", ["order_status"])
    op.create_index(op.f("ix_marketplace_orders_order_currency"), "marketplace_orders", ["order_currency"])
    op.create_index(op.f("ix_marketplace_orders_organization_id"), "marketplace_orders", ["organization_id"])

    op.create_table(
        "marketplace_order_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marketplace_order_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_listing_identifier", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_order_id"], ["marketplace_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_order_line_order_created", "marketplace_order_line_items", ["marketplace_order_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_order_line_listing_created",
        "marketplace_order_line_items",
        ["marketplace_listing_identifier", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_order_line_items_inventory_item_id"), "marketplace_order_line_items", ["inventory_item_id"])
    op.create_index(
        op.f("ix_marketplace_order_line_items_marketplace_listing_identifier"),
        "marketplace_order_line_items",
        ["marketplace_listing_identifier"],
    )
    op.create_index(op.f("ix_marketplace_order_line_items_marketplace_order_id"), "marketplace_order_line_items", ["marketplace_order_id"])

    op.create_table(
        "marketplace_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_order_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("transaction_status", sa.String(length=24), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_currency", sa.String(length=8), nullable=False),
        sa.Column("transaction_reference", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_order_id"], ["marketplace_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "marketplace_order_id",
            "transaction_reference",
            name="uq_marketplace_transaction_reference",
        ),
    )
    op.create_index("ix_mkt_transaction_order_created", "marketplace_transactions", ["marketplace_order_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_transaction_org_status_created",
        "marketplace_transactions",
        ["organization_id", "transaction_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_transactions_marketplace_order_id"), "marketplace_transactions", ["marketplace_order_id"])
    op.create_index(op.f("ix_marketplace_transactions_organization_id"), "marketplace_transactions", ["organization_id"])
    op.create_index(op.f("ix_marketplace_transactions_transaction_currency"), "marketplace_transactions", ["transaction_currency"])
    op.create_index(op.f("ix_marketplace_transactions_transaction_reference"), "marketplace_transactions", ["transaction_reference"])
    op.create_index(op.f("ix_marketplace_transactions_transaction_status"), "marketplace_transactions", ["transaction_status"])
    op.create_index(op.f("ix_marketplace_transactions_transaction_type"), "marketplace_transactions", ["transaction_type"])

    op.create_table(
        "marketplace_order_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_order_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_order_id"], ["marketplace_orders.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_order_event_org_created", "marketplace_order_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_mkt_order_event_order_created", "marketplace_order_events", ["marketplace_order_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_order_event_org_type_created",
        "marketplace_order_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_mkt_order_event_actor_created", "marketplace_order_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_marketplace_order_events_actor_user_id"), "marketplace_order_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_order_events_event_type"), "marketplace_order_events", ["event_type"])
    op.create_index(op.f("ix_marketplace_order_events_marketplace_order_id"), "marketplace_order_events", ["marketplace_order_id"])
    op.create_index(op.f("ix_marketplace_order_events_organization_id"), "marketplace_order_events", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_order_events_organization_id"), table_name="marketplace_order_events")
    op.drop_index(op.f("ix_marketplace_order_events_marketplace_order_id"), table_name="marketplace_order_events")
    op.drop_index(op.f("ix_marketplace_order_events_event_type"), table_name="marketplace_order_events")
    op.drop_index(op.f("ix_marketplace_order_events_actor_user_id"), table_name="marketplace_order_events")
    op.drop_index("ix_mkt_order_event_actor_created", table_name="marketplace_order_events")
    op.drop_index("ix_mkt_order_event_org_type_created", table_name="marketplace_order_events")
    op.drop_index("ix_mkt_order_event_order_created", table_name="marketplace_order_events")
    op.drop_index("ix_mkt_order_event_org_created", table_name="marketplace_order_events")
    op.drop_table("marketplace_order_events")

    op.drop_index(op.f("ix_marketplace_transactions_transaction_type"), table_name="marketplace_transactions")
    op.drop_index(op.f("ix_marketplace_transactions_transaction_status"), table_name="marketplace_transactions")
    op.drop_index(op.f("ix_marketplace_transactions_transaction_reference"), table_name="marketplace_transactions")
    op.drop_index(op.f("ix_marketplace_transactions_transaction_currency"), table_name="marketplace_transactions")
    op.drop_index(op.f("ix_marketplace_transactions_organization_id"), table_name="marketplace_transactions")
    op.drop_index(op.f("ix_marketplace_transactions_marketplace_order_id"), table_name="marketplace_transactions")
    op.drop_index("ix_mkt_transaction_org_status_created", table_name="marketplace_transactions")
    op.drop_index("ix_mkt_transaction_order_created", table_name="marketplace_transactions")
    op.drop_table("marketplace_transactions")

    op.drop_index(op.f("ix_marketplace_order_line_items_marketplace_order_id"), table_name="marketplace_order_line_items")
    op.drop_index(
        op.f("ix_marketplace_order_line_items_marketplace_listing_identifier"),
        table_name="marketplace_order_line_items",
    )
    op.drop_index(op.f("ix_marketplace_order_line_items_inventory_item_id"), table_name="marketplace_order_line_items")
    op.drop_index("ix_mkt_order_line_listing_created", table_name="marketplace_order_line_items")
    op.drop_index("ix_mkt_order_line_order_created", table_name="marketplace_order_line_items")
    op.drop_table("marketplace_order_line_items")

    op.drop_index(op.f("ix_marketplace_orders_organization_id"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_order_currency"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_order_status"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_marketplace_type"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_marketplace_order_identifier"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_marketplace_account_id"), table_name="marketplace_orders")
    op.drop_index(op.f("ix_marketplace_orders_buyer_identifier"), table_name="marketplace_orders")
    op.drop_index("ix_mkt_order_org_status_ordered", table_name="marketplace_orders")
    op.drop_index("ix_mkt_order_org_account_ordered", table_name="marketplace_orders")
    op.drop_index("ix_mkt_order_org_ordered", table_name="marketplace_orders")
    op.drop_table("marketplace_orders")
