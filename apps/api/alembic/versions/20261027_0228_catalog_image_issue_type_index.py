"""Composite index for P104 cover URL preload (issue_id + image_type).

Revision ID: 20261027_0228
Revises: 20261027_0227
"""

from __future__ import annotations

from alembic import op

revision = "20261027_0228"
down_revision = "20261027_0227"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_catalog_image_issue_type",
        "catalog_image",
        ["issue_id", "image_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_image_issue_type", table_name="catalog_image")
