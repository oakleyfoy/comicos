"""Add inventory metadata identity key.

Revision ID: 20260523_0010
Revises: 20260523_0009
Create Date: 2026-05-23 21:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0010"
down_revision: str | None = "20260523_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_copy",
        sa.Column("metadata_identity_key", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_copy", "metadata_identity_key")
