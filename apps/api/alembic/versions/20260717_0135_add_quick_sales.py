"""add quick sales

Revision ID: 20260717_0135
Revises: 20260716_0134
Create Date: 2026-07-17 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0135"
down_revision = "20260716_0134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quick_sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("convention_session_id", sa.Integer(), nullable=True),
        sa.Column("mobile_device_id", sa.Integer(), nullable=True),
        sa.Column("sale_identifier", sa.String(length=128), nullable=False),
        sa.Column("sale_status", sa.String(length=24), nullable=False),
        sa.Column("buyer_label", sa.String(length=200), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("sale_source", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["convention_session_id"], ["convention_sessions.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["mobile_device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "sale_identifier", name="uq_quick_sale_org_identifier"),
    )
    op.create_index("ix_quick_sale_org_created", "quick_sales", ["organization_id", "created_at", "id"])
    op.create_index("ix_quick_sale_org_status_created", "quick_sales", ["organization_id", "sale_status", "created_at", "id"])
    op.create_index("ix_quick_sale_org_source_created", "quick_sales", ["organization_id", "sale_source", "created_at", "id"])
    op.create_index(op.f("ix_quick_sales_organization_id"), "quick_sales", ["organization_id"])
    op.create_index(op.f("ix_quick_sales_convention_session_id"), "quick_sales", ["convention_session_id"])
    op.create_index(op.f("ix_quick_sales_mobile_device_id"), "quick_sales", ["mobile_device_id"])
    op.create_index(op.f("ix_quick_sales_sale_identifier"), "quick_sales", ["sale_identifier"])
    op.create_index(op.f("ix_quick_sales_sale_status"), "quick_sales", ["sale_status"])
    op.create_index(op.f("ix_quick_sales_sale_source"), "quick_sales", ["sale_source"])
    op.create_index(op.f("ix_quick_sales_created_by_user_id"), "quick_sales", ["created_by_user_id"])

    op.create_table(
        "quick_sale_line_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("quick_sale_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("offline_inventory_record_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["offline_inventory_record_id"], ["offline_inventory_records.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["quick_sale_id"], ["quick_sales.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quick_sale_line_item_sale_created", "quick_sale_line_items", ["quick_sale_id", "created_at", "id"])
    op.create_index(
        "ix_quick_sale_line_item_org_status_created",
        "quick_sale_line_items",
        ["organization_id", "line_status", "created_at", "id"],
    )
    op.create_index(
        "ix_quick_sale_line_item_org_inventory_created",
        "quick_sale_line_items",
        ["organization_id", "inventory_item_id", "created_at", "id"],
    )
    op.create_index(op.f("ix_quick_sale_line_items_organization_id"), "quick_sale_line_items", ["organization_id"])
    op.create_index(op.f("ix_quick_sale_line_items_quick_sale_id"), "quick_sale_line_items", ["quick_sale_id"])
    op.create_index(op.f("ix_quick_sale_line_items_inventory_item_id"), "quick_sale_line_items", ["inventory_item_id"])
    op.create_index(
        op.f("ix_quick_sale_line_items_offline_inventory_record_id"),
        "quick_sale_line_items",
        ["offline_inventory_record_id"],
    )
    op.create_index(
        op.f("ix_quick_sale_line_items_marketplace_listing_draft_id"),
        "quick_sale_line_items",
        ["marketplace_listing_draft_id"],
    )
    op.create_index(op.f("ix_quick_sale_line_items_line_status"), "quick_sale_line_items", ["line_status"])

    op.create_table(
        "quick_sale_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("quick_sale_id", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("payment_status", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payment_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["quick_sale_id"], ["quick_sales.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quick_sale_payment_sale_created", "quick_sale_payments", ["quick_sale_id", "created_at", "id"])
    op.create_index(
        "ix_quick_sale_payment_org_status_created",
        "quick_sale_payments",
        ["organization_id", "payment_status", "created_at", "id"],
    )
    op.create_index(
        "ix_quick_sale_payment_org_method_created",
        "quick_sale_payments",
        ["organization_id", "payment_method", "created_at", "id"],
    )
    op.create_index(op.f("ix_quick_sale_payments_organization_id"), "quick_sale_payments", ["organization_id"])
    op.create_index(op.f("ix_quick_sale_payments_quick_sale_id"), "quick_sale_payments", ["quick_sale_id"])
    op.create_index(op.f("ix_quick_sale_payments_payment_method"), "quick_sale_payments", ["payment_method"])
    op.create_index(op.f("ix_quick_sale_payments_payment_status"), "quick_sale_payments", ["payment_status"])

    op.create_table(
        "quick_sale_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("quick_sale_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["quick_sale_id"], ["quick_sales.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quick_sale_event_org_created", "quick_sale_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_quick_sale_event_sale_created", "quick_sale_events", ["quick_sale_id", "created_at", "id"])
    op.create_index(
        "ix_quick_sale_event_org_type_created",
        "quick_sale_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_quick_sale_events_organization_id"), "quick_sale_events", ["organization_id"])
    op.create_index(op.f("ix_quick_sale_events_quick_sale_id"), "quick_sale_events", ["quick_sale_id"])
    op.create_index(op.f("ix_quick_sale_events_actor_user_id"), "quick_sale_events", ["actor_user_id"])
    op.create_index(op.f("ix_quick_sale_events_event_type"), "quick_sale_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_quick_sale_events_event_type"), table_name="quick_sale_events")
    op.drop_index(op.f("ix_quick_sale_events_actor_user_id"), table_name="quick_sale_events")
    op.drop_index(op.f("ix_quick_sale_events_quick_sale_id"), table_name="quick_sale_events")
    op.drop_index(op.f("ix_quick_sale_events_organization_id"), table_name="quick_sale_events")
    op.drop_index("ix_quick_sale_event_org_type_created", table_name="quick_sale_events")
    op.drop_index("ix_quick_sale_event_sale_created", table_name="quick_sale_events")
    op.drop_index("ix_quick_sale_event_org_created", table_name="quick_sale_events")
    op.drop_table("quick_sale_events")

    op.drop_index(op.f("ix_quick_sale_payments_payment_status"), table_name="quick_sale_payments")
    op.drop_index(op.f("ix_quick_sale_payments_payment_method"), table_name="quick_sale_payments")
    op.drop_index(op.f("ix_quick_sale_payments_quick_sale_id"), table_name="quick_sale_payments")
    op.drop_index(op.f("ix_quick_sale_payments_organization_id"), table_name="quick_sale_payments")
    op.drop_index("ix_quick_sale_payment_org_method_created", table_name="quick_sale_payments")
    op.drop_index("ix_quick_sale_payment_org_status_created", table_name="quick_sale_payments")
    op.drop_index("ix_quick_sale_payment_sale_created", table_name="quick_sale_payments")
    op.drop_table("quick_sale_payments")

    op.drop_index(op.f("ix_quick_sale_line_items_line_status"), table_name="quick_sale_line_items")
    op.drop_index(op.f("ix_quick_sale_line_items_marketplace_listing_draft_id"), table_name="quick_sale_line_items")
    op.drop_index(op.f("ix_quick_sale_line_items_offline_inventory_record_id"), table_name="quick_sale_line_items")
    op.drop_index(op.f("ix_quick_sale_line_items_inventory_item_id"), table_name="quick_sale_line_items")
    op.drop_index(op.f("ix_quick_sale_line_items_quick_sale_id"), table_name="quick_sale_line_items")
    op.drop_index(op.f("ix_quick_sale_line_items_organization_id"), table_name="quick_sale_line_items")
    op.drop_index("ix_quick_sale_line_item_org_inventory_created", table_name="quick_sale_line_items")
    op.drop_index("ix_quick_sale_line_item_org_status_created", table_name="quick_sale_line_items")
    op.drop_index("ix_quick_sale_line_item_sale_created", table_name="quick_sale_line_items")
    op.drop_table("quick_sale_line_items")

    op.drop_index(op.f("ix_quick_sales_created_by_user_id"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_sale_source"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_sale_status"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_sale_identifier"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_mobile_device_id"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_convention_session_id"), table_name="quick_sales")
    op.drop_index(op.f("ix_quick_sales_organization_id"), table_name="quick_sales")
    op.drop_index("ix_quick_sale_org_source_created", table_name="quick_sales")
    op.drop_index("ix_quick_sale_org_status_created", table_name="quick_sales")
    op.drop_index("ix_quick_sale_org_created", table_name="quick_sales")
    op.drop_table("quick_sales")
