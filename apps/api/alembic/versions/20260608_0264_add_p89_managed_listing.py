"""Add P89 managed listings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0264"
down_revision = "20260608_0263"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p89_managed_listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("listing_draft_id", sa.Integer(), nullable=True),
        sa.Column("marketplace", sa.String(length=16), nullable=False),
        sa.Column("listing_url", sa.String(length=2048), nullable=False),
        sa.Column("external_listing_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("asking_price", sa.Float(), nullable=True),
        sa.Column("shipping_price", sa.Float(), nullable=True),
        sa.Column("minimum_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_price", sa.Float(), nullable=True),
        sa.Column("shipping_charged", sa.Float(), nullable=True),
        sa.Column("marketplace_fees", sa.Float(), nullable=True),
        sa.Column("shipping_cost", sa.Float(), nullable=True),
        sa.Column("net_profit", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status_history_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_draft_id"], ["p89_listing_draft.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_p89_managed_listing_owner_user_id"), "p89_managed_listing", ["owner_user_id"])
    op.create_index(op.f("ix_p89_managed_listing_inventory_copy_id"), "p89_managed_listing", ["inventory_copy_id"])
    op.create_index(op.f("ix_p89_managed_listing_listing_draft_id"), "p89_managed_listing", ["listing_draft_id"])
    op.create_index(op.f("ix_p89_managed_listing_marketplace"), "p89_managed_listing", ["marketplace"])
    op.create_index(op.f("ix_p89_managed_listing_status"), "p89_managed_listing", ["status"])
    op.create_index("ix_p89_mlist_owner_status", "p89_managed_listing", ["owner_user_id", "status"])
    op.create_index("ix_p89_mlist_owner_copy", "p89_managed_listing", ["owner_user_id", "inventory_copy_id"])
    op.create_index("ix_p89_mlist_owner_listed", "p89_managed_listing", ["owner_user_id", "listed_at"])


def downgrade() -> None:
    op.drop_index("ix_p89_mlist_owner_listed", table_name="p89_managed_listing")
    op.drop_index("ix_p89_mlist_owner_copy", table_name="p89_managed_listing")
    op.drop_index("ix_p89_mlist_owner_status", table_name="p89_managed_listing")
    op.drop_index(op.f("ix_p89_managed_listing_status"), table_name="p89_managed_listing")
    op.drop_index(op.f("ix_p89_managed_listing_marketplace"), table_name="p89_managed_listing")
    op.drop_index(op.f("ix_p89_managed_listing_listing_draft_id"), table_name="p89_managed_listing")
    op.drop_index(op.f("ix_p89_managed_listing_inventory_copy_id"), table_name="p89_managed_listing")
    op.drop_index(op.f("ix_p89_managed_listing_owner_user_id"), table_name="p89_managed_listing")
    op.drop_table("p89_managed_listing")
