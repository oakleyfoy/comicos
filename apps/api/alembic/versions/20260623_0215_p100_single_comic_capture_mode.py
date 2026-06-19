"""P100 single-comic capture mode on photo import sessions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260623_0215"
down_revision = "20260622_0214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_session",
        sa.Column("capture_mode", sa.String(length=32), nullable=False, server_default="single_comic"),
    )


def downgrade() -> None:
    op.drop_column("photo_import_session", "capture_mode")
