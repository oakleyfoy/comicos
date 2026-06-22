"""Inventory catalog unification Phase 4: order financial provenance snapshot.

Adds nullable provenance columns to inventory_copy so purchase history
(retailer, date, item price, shipping, tax, source) survives a future teardown
of the legacy customer_order / order_item tables. Additive + nullable => fully
reversible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260625_0100"
down_revision = "20260624_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_copy", sa.Column("order_retailer", sa.String(length=255), nullable=True))
    op.add_column("inventory_copy", sa.Column("order_date", sa.Date(), nullable=True))
    op.add_column("inventory_copy", sa.Column("order_source_type", sa.String(length=64), nullable=True))
    op.add_column("inventory_copy", sa.Column("order_raw_item_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("inventory_copy", sa.Column("order_shipping_paid", sa.Numeric(12, 2), nullable=True))
    op.add_column("inventory_copy", sa.Column("order_tax_paid", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_copy", "order_tax_paid")
    op.drop_column("inventory_copy", "order_shipping_paid")
    op.drop_column("inventory_copy", "order_raw_item_price")
    op.drop_column("inventory_copy", "order_source_type")
    op.drop_column("inventory_copy", "order_date")
    op.drop_column("inventory_copy", "order_retailer")
