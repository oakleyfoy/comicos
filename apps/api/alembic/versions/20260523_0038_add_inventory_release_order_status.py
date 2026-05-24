"""Add inventory release and order status fields.

Revision ID: 20260523_0038
Revises: 20260523_0037
Create Date: 2026-06-08 03:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0038"
down_revision: str | None = "20260523_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_copy",
        sa.Column("release_status", sa.String(length=30), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "inventory_copy",
        sa.Column("order_status", sa.String(length=20), nullable=False, server_default="ordered"),
    )
    op.add_column("inventory_copy", sa.Column("expected_ship_date", sa.Date(), nullable=True))
    op.add_column("inventory_copy", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_inventory_copy_release_status"),
        "inventory_copy",
        ["release_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_copy_order_status"),
        "inventory_copy",
        ["order_status"],
        unique=False,
    )
    op.execute(
        """
        UPDATE inventory_copy
        SET release_status = CASE
            WHEN release_date IS NULL THEN 'unknown'
            WHEN release_date > CURRENT_DATE THEN 'not_released_yet'
            ELSE 'released'
        END
        """
    )
    op.execute(
        """
        UPDATE inventory_copy
        SET order_status = CASE
            WHEN release_status = 'not_released_yet' THEN 'preordered'
            ELSE 'received'
        END
        """
    )
    op.alter_column("inventory_copy", "release_status", server_default=None)
    op.alter_column("inventory_copy", "order_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_copy_order_status"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_release_status"), table_name="inventory_copy")
    op.drop_column("inventory_copy", "received_at")
    op.drop_column("inventory_copy", "expected_ship_date")
    op.drop_column("inventory_copy", "order_status")
    op.drop_column("inventory_copy", "release_status")
