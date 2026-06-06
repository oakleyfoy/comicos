"""add p78 sell workflow listing drafts

Revision ID: 20260607_0249
Revises: 20260607_0248
Create Date: 2026-06-07 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0249"
down_revision = "20260607_0248"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p78_listing_draft",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition_suggested", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("shipping_recommendation", sa.String(length=120), nullable=False),
        sa.Column("suggested_sell_quantity", sa.Integer(), nullable=False),
        sa.Column("fmv_at_generation", sa.Float(), nullable=False),
        sa.Column("quick_sale_price", sa.Float(), nullable=False),
        sa.Column("market_price", sa.Float(), nullable=False),
        sa.Column("premium_price", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=False),
        sa.Column("bundle_key", sa.String(length=256), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p78_draft_owner_status", "p78_listing_draft", ["owner_user_id", "status", "updated_at", "id"])
    op.create_index("ix_p78_draft_owner_copy", "p78_listing_draft", ["owner_user_id", "inventory_copy_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_p78_draft_owner_copy", table_name="p78_listing_draft")
    op.drop_index("ix_p78_draft_owner_status", table_name="p78_listing_draft")
    op.drop_table("p78_listing_draft")
