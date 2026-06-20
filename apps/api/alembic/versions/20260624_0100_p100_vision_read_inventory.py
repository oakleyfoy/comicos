"""P100 added_to_inventory flag on vision reads."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260624_0100"
down_revision = "20260623_0218"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_vision_read",
        sa.Column("added_to_inventory", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("photo_import_vision_read", "added_to_inventory")
