"""add p80 mobile scan platform

Revision ID: 20260607_0245
Revises: 20260607_0244
Create Date: 2026-06-07 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0245"
down_revision = "20260607_0244"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p80_mobile_scan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_source", sa.String(length=24), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("normalized_barcode", sa.String(length=128), nullable=False),
        sa.Column("image_reference", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("requires_manual_review", sa.Boolean(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("book_identity_key", sa.String(length=512), nullable=False),
        sa.Column("identification_json", sa.JSON(), nullable=False),
        sa.Column("result_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p80_mobile_scan_owner_created", "p80_mobile_scan", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_p80_mobile_scan_owner_barcode", "p80_mobile_scan", ["owner_user_id", "normalized_barcode", "id"])
    op.create_index(op.f("ix_p80_mobile_scan_owner_user_id"), "p80_mobile_scan", ["owner_user_id"])
    op.create_index(op.f("ix_p80_mobile_scan_scan_source"), "p80_mobile_scan", ["scan_source"])
    op.create_index(op.f("ix_p80_mobile_scan_normalized_barcode"), "p80_mobile_scan", ["normalized_barcode"])
    op.create_index(op.f("ix_p80_mobile_scan_confidence"), "p80_mobile_scan", ["confidence"])
    op.create_index(op.f("ix_p80_mobile_scan_inventory_copy_id"), "p80_mobile_scan", ["inventory_copy_id"])
    op.create_index(op.f("ix_p80_mobile_scan_book_identity_key"), "p80_mobile_scan", ["book_identity_key"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p80_mobile_scan_book_identity_key"), table_name="p80_mobile_scan")
    op.drop_index(op.f("ix_p80_mobile_scan_inventory_copy_id"), table_name="p80_mobile_scan")
    op.drop_index(op.f("ix_p80_mobile_scan_confidence"), table_name="p80_mobile_scan")
    op.drop_index(op.f("ix_p80_mobile_scan_normalized_barcode"), table_name="p80_mobile_scan")
    op.drop_index(op.f("ix_p80_mobile_scan_scan_source"), table_name="p80_mobile_scan")
    op.drop_index(op.f("ix_p80_mobile_scan_owner_user_id"), table_name="p80_mobile_scan")
    op.drop_index("ix_p80_mobile_scan_owner_barcode", table_name="p80_mobile_scan")
    op.drop_index("ix_p80_mobile_scan_owner_created", table_name="p80_mobile_scan")
    op.drop_table("p80_mobile_scan")
