"""P98 acquisitions table + inventory_copy acquisition linkage and legacy backfill."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_0204"
down_revision = "20260619_0203"
branch_labels = None
depends_on = None


LEGACY_SELLER_NAME = "Legacy / Unknown Source"


def upgrade() -> None:
    op.create_table(
        "acquisitions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("acquisition_type", sa.String(length=40), nullable=False, server_default="UNKNOWN"),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("seller_name", sa.String(length=255), nullable=True),
        sa.Column("seller_username", sa.String(length=255), nullable=True),
        sa.Column("total_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shipping_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expected_book_count", sa.Integer(), nullable=True),
        sa.Column("actual_book_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("allocation_mode", sa.String(length=16), nullable=False, server_default="EVEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )
    op.create_index("ix_acquisitions_user_id", "acquisitions", ["user_id"])
    op.create_index("ix_acquisitions_acquisition_type", "acquisitions", ["acquisition_type"])
    op.create_index("ix_acquisitions_purchase_date", "acquisitions", ["purchase_date"])
    op.create_index("ix_acquisitions_status", "acquisitions", ["status"])

    op.add_column(
        "inventory_copy",
        sa.Column("acquisition_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "inventory_copy",
        sa.Column("variant_status", sa.String(length=20), nullable=False, server_default="RESOLVED"),
    )
    op.create_foreign_key(
        "fk_inventory_copy_acquisition_id",
        "inventory_copy",
        "acquisitions",
        ["acquisition_id"],
        ["id"],
    )
    op.create_index("ix_inventory_copy_acquisition_id", "inventory_copy", ["acquisition_id"])
    op.create_index("ix_inventory_copy_variant_status", "inventory_copy", ["variant_status"])

    # Manual catalog-issue adds (P98) do not need the synthetic Order/Variant graph.
    op.alter_column("inventory_copy", "order_item_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("inventory_copy", "variant_id", existing_type=sa.Integer(), nullable=True)

    # Backfill: one Legacy/Unknown acquisition per user, then link existing copies (P98-01).
    op.execute(
        sa.text(
            """
            INSERT INTO acquisitions (
                user_id, acquisition_type, seller_name, total_paid, shipping_paid,
                tax_paid, actual_book_count, status, allocation_mode, created_at, updated_at
            )
            SELECT DISTINCT ic.user_id, 'UNKNOWN', :seller, 0, 0, 0, 0, 'COMPLETE', 'EVEN', now(), now()
            FROM inventory_copy ic
            WHERE ic.user_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM acquisitions a
                  WHERE a.user_id = ic.user_id AND a.seller_name = :seller
              )
            """
        ).bindparams(seller=LEGACY_SELLER_NAME)
    )
    op.execute(
        sa.text(
            """
            UPDATE inventory_copy AS ic
            SET acquisition_id = a.id
            FROM acquisitions AS a
            WHERE a.user_id = ic.user_id
              AND a.seller_name = :seller
              AND ic.acquisition_id IS NULL
              AND ic.user_id IS NOT NULL
            """
        ).bindparams(seller=LEGACY_SELLER_NAME)
    )
    op.execute(
        sa.text(
            """
            UPDATE acquisitions AS a
            SET actual_book_count = (
                SELECT COUNT(*) FROM inventory_copy ic WHERE ic.acquisition_id = a.id
            )
            WHERE a.seller_name = :seller
            """
        ).bindparams(seller=LEGACY_SELLER_NAME)
    )


def downgrade() -> None:
    op.alter_column("inventory_copy", "variant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("inventory_copy", "order_item_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_inventory_copy_variant_status", table_name="inventory_copy")
    op.drop_index("ix_inventory_copy_acquisition_id", table_name="inventory_copy")
    op.drop_constraint("fk_inventory_copy_acquisition_id", "inventory_copy", type_="foreignkey")
    op.drop_column("inventory_copy", "variant_status")
    op.drop_column("inventory_copy", "acquisition_id")
    op.drop_index("ix_acquisitions_status", table_name="acquisitions")
    op.drop_index("ix_acquisitions_purchase_date", table_name="acquisitions")
    op.drop_index("ix_acquisitions_acquisition_type", table_name="acquisitions")
    op.drop_index("ix_acquisitions_user_id", table_name="acquisitions")
    op.drop_table("acquisitions")
