"""add external catalog image url columns

Revision ID: 20261009_0215
Revises: 20261008_0214
Create Date: 2026-10-09 02:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261009_0215"
down_revision = "20261008_0214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_catalog_issue",
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "external_catalog_issue",
        sa.Column("high_resolution_image_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_catalog_issue", "high_resolution_image_url")
    op.drop_column("external_catalog_issue", "thumbnail_url")
