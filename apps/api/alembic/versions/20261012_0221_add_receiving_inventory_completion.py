"""add receiving inventory completion

Revision ID: 20261012_0221
Revises: 20261012_0220
Create Date: 2026-10-12 02:21:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0221"
down_revision = "20261012_0220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_order", sa.Column("seller_name", sa.String(length=255), nullable=True))
    op.add_column("customer_order", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column(
        "receiving_session",
        sa.Column("purchase_order_id", sa.Integer(), nullable=True),
    )
    op.add_column("receiving_session", sa.Column("purchase_mode", sa.String(length=20), nullable=True))
    op.add_column("receiving_session", sa.Column("purchase_source_type", sa.String(length=40), nullable=True))
    op.add_column("receiving_session", sa.Column("purchase_label", sa.String(length=255), nullable=True))
    op.add_column("receiving_session", sa.Column("seller_name", sa.String(length=255), nullable=True))
    op.add_column("receiving_session", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.add_column("receiving_session", sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True))
    op.add_column("receiving_session", sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("receiving_session", sa.Column("tax_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("receiving_session", sa.Column("purchase_notes", sa.Text(), nullable=True))
    op.add_column("receiving_session", sa.Column("allocation_method", sa.String(length=32), nullable=True))
    op.add_column("receiving_session", sa.Column("allocation_details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("receiving_session", sa.Column("inventory_created_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_receiving_session_purchase_order_id", "receiving_session", ["purchase_order_id"])
    op.create_index("ix_receiving_session_purchase_mode", "receiving_session", ["purchase_mode"])
    op.create_index("ix_receiving_session_purchase_source_type", "receiving_session", ["purchase_source_type"])
    op.create_index("ix_receiving_session_allocation_method", "receiving_session", ["allocation_method"])
    op.create_foreign_key(
        "fk_receiving_session_purchase_order_id_customer_order",
        "receiving_session",
        "customer_order",
        ["purchase_order_id"],
        ["id"],
    )

    op.add_column("receiving_session_item", sa.Column("inventory_copy_id", sa.Integer(), nullable=True))
    op.create_index("ix_receiving_session_item_inventory_copy_id", "receiving_session_item", ["inventory_copy_id"])
    op.create_foreign_key(
        "fk_receiving_session_item_inventory_copy_id_inventory_copy",
        "receiving_session_item",
        "inventory_copy",
        ["inventory_copy_id"],
        ["id"],
    )

    op.add_column("inventory_copy", sa.Column("receiving_session_id", sa.Integer(), nullable=True))
    op.add_column(
        "inventory_copy",
        sa.Column("received_via", sa.String(length=40), nullable=False, server_default="RECEIVING_STATION"),
    )
    op.create_index("ix_inventory_copy_receiving_session_id", "inventory_copy", ["receiving_session_id"])
    op.create_index("ix_inventory_copy_received_via", "inventory_copy", ["received_via"])
    op.create_foreign_key(
        "fk_inventory_copy_receiving_session_id_receiving_session",
        "inventory_copy",
        "receiving_session",
        ["receiving_session_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_copy_receiving_session_id_receiving_session",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_index("ix_inventory_copy_received_via", table_name="inventory_copy")
    op.drop_index("ix_inventory_copy_receiving_session_id", table_name="inventory_copy")
    op.drop_column("inventory_copy", "received_via")
    op.drop_column("inventory_copy", "receiving_session_id")

    op.drop_constraint(
        "fk_receiving_session_item_inventory_copy_id_inventory_copy",
        "receiving_session_item",
        type_="foreignkey",
    )
    op.drop_index("ix_receiving_session_item_inventory_copy_id", table_name="receiving_session_item")
    op.drop_column("receiving_session_item", "inventory_copy_id")

    op.drop_constraint(
        "fk_receiving_session_purchase_order_id_customer_order",
        "receiving_session",
        type_="foreignkey",
    )
    op.drop_index("ix_receiving_session_allocation_method", table_name="receiving_session")
    op.drop_index("ix_receiving_session_purchase_source_type", table_name="receiving_session")
    op.drop_index("ix_receiving_session_purchase_mode", table_name="receiving_session")
    op.drop_index("ix_receiving_session_purchase_order_id", table_name="receiving_session")
    op.drop_column("receiving_session", "inventory_created_count")
    op.drop_column("receiving_session", "allocation_details_json")
    op.drop_column("receiving_session", "allocation_method")
    op.drop_column("receiving_session", "purchase_notes")
    op.drop_column("receiving_session", "tax_amount")
    op.drop_column("receiving_session", "shipping_amount")
    op.drop_column("receiving_session", "amount_paid")
    op.drop_column("receiving_session", "purchase_date")
    op.drop_column("receiving_session", "seller_name")
    op.drop_column("receiving_session", "purchase_label")
    op.drop_column("receiving_session", "purchase_source_type")
    op.drop_column("receiving_session", "purchase_mode")
    op.drop_column("receiving_session", "purchase_order_id")

    op.drop_column("customer_order", "notes")
    op.drop_column("customer_order", "seller_name")
