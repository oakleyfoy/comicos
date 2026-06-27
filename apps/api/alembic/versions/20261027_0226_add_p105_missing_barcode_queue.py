"""P105 missing barcode repair queue."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261027_0226"
down_revision = "20261012_0225"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p105_missing_barcode_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("publisher_guess", sa.String(length=256), nullable=True),
        sa.Column("issue_number_from_supplement", sa.String(length=32), nullable=True),
        sa.Column("intake_item_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chosen_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("created_catalog_upc_id", sa.Integer(), nullable=True),
        sa.Column("created_learned_barcode_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["intake_item_id"], ["intake_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p105_missing_barcode_queue_barcode", "p105_missing_barcode_queue", ["barcode"])
    op.create_index(
        "ix_p105_missing_barcode_queue_intake_item_id",
        "p105_missing_barcode_queue",
        ["intake_item_id"],
    )
    op.create_index("ix_p105_missing_barcode_queue_status", "p105_missing_barcode_queue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_p105_missing_barcode_queue_status", table_name="p105_missing_barcode_queue")
    op.drop_index("ix_p105_missing_barcode_queue_intake_item_id", table_name="p105_missing_barcode_queue")
    op.drop_index("ix_p105_missing_barcode_queue_barcode", table_name="p105_missing_barcode_queue")
    op.drop_table("p105_missing_barcode_queue")
