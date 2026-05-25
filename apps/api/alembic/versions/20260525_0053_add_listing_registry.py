"""P36 listing registry foundation (canonical listing truth layer).

Revision ID: 20260525_0053
Revises: 20260525_0052
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0053"
down_revision: str | None = "20260525_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_summary", sa.Text(), nullable=True),
        sa.Column("asking_price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("asking_price_currency", sa.String(length=8), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_listing_owner_user_replay_key"),
    )
    op.create_index("ix_listing_owner_user_id_status", "listing", ["owner_user_id", "status"], unique=False)
    op.create_index(op.f("ix_listing_inventory_copy_id"), "listing", ["inventory_copy_id"], unique=False)

    op.create_table(
        "listing_inventory_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("quantity_allocated", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", name="uq_listing_inventory_link_single_listing"),
    )
    op.create_index(op.f("ix_listing_inventory_link_listing_id"), "listing_inventory_link", ["listing_id"], unique=False)
    op.create_index(
        op.f("ix_listing_inventory_link_inventory_copy_id"),
        "listing_inventory_link",
        ["inventory_copy_id"],
        unique=False,
    )

    op.create_table(
        "listing_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=True),
        sa.Column("scan_session_item_id", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["scan_session_item_id"], ["scan_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "display_order", name="uq_listing_image_display_order"),
    )
    op.create_index(op.f("ix_listing_image_listing_id"), "listing_image", ["listing_id"], unique=False)

    op.create_table(
        "listing_lifecycle_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("prior_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "replay_key", name="uq_listing_lifecycle_event_listing_replay_key"),
    )
    op.create_index(
        "ix_listing_lifecycle_event_listing_id_created_at_id",
        "listing_lifecycle_event",
        ["listing_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "listing_price_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("prior_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=True),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "replay_key", name="uq_listing_price_history_listing_replay_key"),
    )
    op.create_index(
        "ix_listing_price_history_listing_id_created_at_id",
        "listing_price_history",
        ["listing_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_listing_price_history_listing_id_created_at_id", table_name="listing_price_history")
    op.drop_table("listing_price_history")

    op.drop_index("ix_listing_lifecycle_event_listing_id_created_at_id", table_name="listing_lifecycle_event")
    op.drop_table("listing_lifecycle_event")

    op.drop_index(op.f("ix_listing_image_listing_id"), table_name="listing_image")
    op.drop_table("listing_image")

    op.drop_index(op.f("ix_listing_inventory_link_inventory_copy_id"), table_name="listing_inventory_link")
    op.drop_index(op.f("ix_listing_inventory_link_listing_id"), table_name="listing_inventory_link")
    op.drop_table("listing_inventory_link")

    op.drop_index(op.f("ix_listing_inventory_copy_id"), table_name="listing")
    op.drop_index("ix_listing_owner_user_id_status", table_name="listing")
    op.drop_table("listing")
