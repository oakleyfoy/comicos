"""Add P89 listing drafts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0263"
down_revision = "20260608_0262"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p89_listing_draft",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("sell_candidate_id", sa.Integer(), nullable=True),
        sa.Column("market_price_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("marketplace", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition_notes", sa.Text(), nullable=False),
        sa.Column("shipping_notes", sa.Text(), nullable=False),
        sa.Column("suggested_price", sa.Float(), nullable=True),
        sa.Column("minimum_price", sa.Float(), nullable=True),
        sa.Column("premium_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["sell_candidate_id"], ["p89_sell_candidate.id"]),
        sa.ForeignKeyConstraint(["market_price_snapshot_id"], ["p89_market_price_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_p89_listing_draft_owner_user_id"), "p89_listing_draft", ["owner_user_id"])
    op.create_index(op.f("ix_p89_listing_draft_inventory_copy_id"), "p89_listing_draft", ["inventory_copy_id"])
    op.create_index(op.f("ix_p89_listing_draft_marketplace"), "p89_listing_draft", ["marketplace"])
    op.create_index(op.f("ix_p89_listing_draft_status"), "p89_listing_draft", ["status"])
    op.create_index("ix_p89_list_draft_owner_status", "p89_listing_draft", ["owner_user_id", "status"])
    op.create_index("ix_p89_list_draft_owner_copy", "p89_listing_draft", ["owner_user_id", "inventory_copy_id"])


def downgrade() -> None:
    op.drop_index("ix_p89_list_draft_owner_copy", table_name="p89_listing_draft")
    op.drop_index("ix_p89_list_draft_owner_status", table_name="p89_listing_draft")
    op.drop_index(op.f("ix_p89_listing_draft_status"), table_name="p89_listing_draft")
    op.drop_index(op.f("ix_p89_listing_draft_marketplace"), table_name="p89_listing_draft")
    op.drop_index(op.f("ix_p89_listing_draft_inventory_copy_id"), table_name="p89_listing_draft")
    op.drop_index(op.f("ix_p89_listing_draft_owner_user_id"), table_name="p89_listing_draft")
    op.drop_table("p89_listing_draft")
