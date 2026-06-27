"""P106 barcode gap resolution queue."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261027_0229"
down_revision = "20261027_0228"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "barcode_gap_resolution_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("normalized_barcode", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("gcd_issue_id", sa.Integer(), nullable=True),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("catalog_upc_id", sa.Integer(), nullable=True),
        sa.Column("scanner_session_id", sa.Integer(), nullable=True),
        sa.Column("photo_import_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_barcode_gap_resolution_queue_barcode", "barcode_gap_resolution_queue", ["barcode"])
    op.create_index(
        "ix_barcode_gap_resolution_queue_normalized_barcode",
        "barcode_gap_resolution_queue",
        ["normalized_barcode"],
    )
    op.create_index("ix_barcode_gap_resolution_queue_status", "barcode_gap_resolution_queue", ["status"])
    op.create_index(
        "ix_barcode_gap_resolution_queue_gcd_issue_id",
        "barcode_gap_resolution_queue",
        ["gcd_issue_id"],
    )
    op.create_index(
        "ix_barcode_gap_resolution_queue_catalog_issue_id",
        "barcode_gap_resolution_queue",
        ["catalog_issue_id"],
    )
    op.create_index(
        "ix_barcode_gap_resolution_queue_scanner_session_id",
        "barcode_gap_resolution_queue",
        ["scanner_session_id"],
    )
    op.create_index(
        "ix_barcode_gap_resolution_queue_photo_import_id",
        "barcode_gap_resolution_queue",
        ["photo_import_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_barcode_gap_resolution_queue_photo_import_id", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_scanner_session_id", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_catalog_issue_id", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_gcd_issue_id", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_status", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_normalized_barcode", table_name="barcode_gap_resolution_queue")
    op.drop_index("ix_barcode_gap_resolution_queue_barcode", table_name="barcode_gap_resolution_queue")
    op.drop_table("barcode_gap_resolution_queue")
