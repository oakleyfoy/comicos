"""Add eBay comp normalization and import history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260606_0232"
down_revision = "20260605_0231"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ebay_comp_record",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_listing_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.String(length=510), nullable=False),
        sa.Column("sold_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("condition", sa.String(length=255), nullable=True),
        sa.Column("listing_type", sa.String(length=64), nullable=True),
        sa.Column("item_url", sa.String(length=1024), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "provider", "provider_listing_id", name="uq_ebay_comp_owner_provider_listing"),
    )
    op.create_index("ix_ebay_comp_owner_imported", "ebay_comp_record", ["owner_user_id", "imported_at", "id"])
    op.create_index("ix_ebay_comp_provider_listing", "ebay_comp_record", ["provider", "provider_listing_id", "id"])

    op.create_table(
        "ebay_comp_import_run",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("import_status", sa.String(length=24), nullable=False),
        sa.Column("search_criteria_json", sa.JSON(), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ebay_comp_import_owner_imported", "ebay_comp_import_run", ["owner_user_id", "imported_at", "id"])
    op.create_index(
        "ix_ebay_comp_import_owner_status_imported",
        "ebay_comp_import_run",
        ["owner_user_id", "import_status", "imported_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ebay_comp_import_owner_status_imported", table_name="ebay_comp_import_run")
    op.drop_index("ix_ebay_comp_import_owner_imported", table_name="ebay_comp_import_run")
    op.drop_table("ebay_comp_import_run")

    op.drop_index("ix_ebay_comp_provider_listing", table_name="ebay_comp_record")
    op.drop_index("ix_ebay_comp_owner_imported", table_name="ebay_comp_record")
    op.drop_table("ebay_comp_record")
