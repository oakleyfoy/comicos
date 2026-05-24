"""Add OCR result processing_started_at for stale detection.

Revision ID: 20260523_0033
Revises: 20260523_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0033"
down_revision: str | None = "20260523_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cover_image_ocr_result", "processing_started_at")
