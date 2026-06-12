"""add retailer order catalog enrichment fields

Revision ID: 20260612_0299
Revises: 445f6d952d77
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260612_0299"
down_revision = "445f6d952d77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_item", sa.Column("catalog_match_id", sa.Integer(), nullable=True))
    op.add_column("order_item", sa.Column("enrichment_status", sa.String(length=32), nullable=True))
    op.add_column("order_item", sa.Column("enrichment_confidence", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("order_item", sa.Column("enrichment_notes", sa.Text(), nullable=True))
    op.add_column("order_item", sa.Column("foc_date", sa.Date(), nullable=True))
    op.create_index("ix_order_item_enrichment_status", "order_item", ["enrichment_status"], unique=False)

    op.add_column("inventory_copy", sa.Column("source_image_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_copy", "source_image_url")
    op.drop_index("ix_order_item_enrichment_status", table_name="order_item")
    op.drop_column("order_item", "foc_date")
    op.drop_column("order_item", "enrichment_notes")
    op.drop_column("order_item", "enrichment_confidence")
    op.drop_column("order_item", "enrichment_status")
    op.drop_column("order_item", "catalog_match_id")
