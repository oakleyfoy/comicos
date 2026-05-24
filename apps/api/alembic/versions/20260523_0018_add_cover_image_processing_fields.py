"""Add deterministic cover image processing status fields.

Revision ID: 20260523_0018
Revises: 20260523_0017
Create Date: 2026-05-24 15:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0018"
down_revision: str | None = "20260523_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image",
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "cover_image",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "cover_image",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cover_image",
        sa.Column("metadata_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_cover_image_processing_status"),
        "cover_image",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cover_image_processing_status"), table_name="cover_image")
    op.drop_column("cover_image", "metadata_refreshed_at")
    op.drop_column("cover_image", "processed_at")
    op.drop_column("cover_image", "processing_error")
    op.drop_column("cover_image", "processing_status")
