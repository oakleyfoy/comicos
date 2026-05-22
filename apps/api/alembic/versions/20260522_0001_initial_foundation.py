"""Initial database foundation.

Revision ID: 20260522_0001
Revises:
Create Date: 2026-05-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publisher",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_publisher_name"), "publisher", ["name"], unique=False)

    op.create_table(
        "customer_order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retailer", sa.String(length=255), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "comic_title",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["publisher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comic_title_name"), "comic_title", ["name"], unique=False)
    op.create_index(
        op.f("ix_comic_title_publisher_id"),
        "comic_title",
        ["publisher_id"],
        unique=False,
    )

    op.create_table(
        "comic_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comic_title_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.String(length=50), nullable=False),
        sa.Column("cover_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comic_title_id"], ["comic_title.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comic_issue_comic_title_id"),
        "comic_issue",
        ["comic_title_id"],
        unique=False,
    )

    op.create_table(
        "variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comic_issue_id", sa.Integer(), nullable=False),
        sa.Column("cover_name", sa.String(length=255), nullable=True),
        sa.Column("printing", sa.String(length=100), nullable=True),
        sa.Column("ratio", sa.String(length=100), nullable=True),
        sa.Column("variant_type", sa.String(length=100), nullable=True),
        sa.Column("cover_artist", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comic_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_variant_comic_issue_id"),
        "variant",
        ["comic_issue_id"],
        unique=False,
    )

    op.create_table(
        "order_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("raw_item_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("allocated_shipping", sa.Numeric(12, 2), nullable=False),
        sa.Column("allocated_tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("all_in_unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_item_order_id"), "order_item", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_item_variant_id"), "order_item", ["variant_id"], unique=False)

    op.create_table(
        "inventory_copy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("copy_number", sa.Integer(), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("condition_notes", sa.String(), nullable=True),
        sa.Column("grade_status", sa.String(length=50), nullable=False),
        sa.Column("hold_status", sa.String(length=50), nullable=False),
        sa.Column("current_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("star_rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_item.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_copy_order_item_id"),
        "inventory_copy",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_copy_variant_id"),
        "inventory_copy",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("inventory_copy")

    op.drop_table("order_item")

    op.drop_table("variant")

    op.drop_table("comic_issue")

    op.drop_table("comic_title")

    op.drop_table("customer_order")
    op.drop_table("publisher")
