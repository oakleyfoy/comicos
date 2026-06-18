"""P100-14 candidate thumbnail_url."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260621_0213"
down_revision = "20260621_0212"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_candidate",
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("photo_import_candidate", "thumbnail_url")
