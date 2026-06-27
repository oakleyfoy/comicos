"""P104: track last hydration run on cover assets.

Revision ID: 20261027_0227
Revises: 20261027_0226
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261027_0227"
down_revision = "20261027_0226"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_cover_assets",
        sa.Column("last_hydration_run_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_catalog_cover_assets_last_hydration_run_id",
        "catalog_cover_assets",
        ["last_hydration_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_cover_assets_last_hydration_run_id", table_name="catalog_cover_assets")
    op.drop_column("catalog_cover_assets", "last_hydration_run_id")
