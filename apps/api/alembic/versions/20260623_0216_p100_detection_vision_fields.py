"""P100-22 vision-first detection fields (barcode + recognition mode)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260623_0216"
down_revision = "20260623_0215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_barcode", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("recognition_mode", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("photo_import_detected_book", "recognition_mode")
    op.drop_column("photo_import_detected_book", "ai_barcode")
