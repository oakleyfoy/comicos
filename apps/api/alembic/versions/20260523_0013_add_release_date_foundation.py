"""Add release date enrichment foundation.

Revision ID: 20260523_0013
Revises: 20260523_0012
Create Date: 2026-05-24 00:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0013"
down_revision: str | None = "20260523_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "canonical_series",
        sa.Column("earliest_known_release_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "canonical_series",
        sa.Column("latest_known_release_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "inventory_copy",
        sa.Column("release_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "inventory_copy",
        sa.Column("release_year", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_copy", "release_year")
    op.drop_column("inventory_copy", "release_date")
    op.drop_column("canonical_series", "latest_known_release_date")
    op.drop_column("canonical_series", "earliest_known_release_date")
