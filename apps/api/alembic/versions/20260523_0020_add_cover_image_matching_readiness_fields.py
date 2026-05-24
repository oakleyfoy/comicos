"""Add cover image matching readiness fields.

Revision ID: 20260523_0020
Revises: 20260523_0019
Create Date: 2026-05-24 17:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0020"
down_revision: str | None = "20260523_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image",
        sa.Column(
            "matching_status",
            sa.String(length=20),
            nullable=False,
            server_default="not_ready",
        ),
    )
    op.add_column("cover_image", sa.Column("matching_notes", sa.Text(), nullable=True))
    op.add_column(
        "cover_image",
        sa.Column("ready_for_matching_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_cover_image_matching_status"),
        "cover_image",
        ["matching_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cover_image_matching_status"), table_name="cover_image")
    op.drop_column("cover_image", "ready_for_matching_at")
    op.drop_column("cover_image", "matching_notes")
    op.drop_column("cover_image", "matching_status")
