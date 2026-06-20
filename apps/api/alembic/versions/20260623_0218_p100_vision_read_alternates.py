"""P100-25 possible_alternates on vision reads."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260623_0218"
down_revision = "20260623_0217"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_vision_read",
        sa.Column("possible_alternates", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("photo_import_vision_read", "possible_alternates")
