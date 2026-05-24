"""Add primary_cover_image_id on inventory_copy and draft_import.

Revision ID: 20260523_0017
Revises: 20260523_0016
Create Date: 2026-05-24 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0017"
down_revision: str | None = "20260523_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_copy",
        sa.Column("primary_cover_image_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_copy_primary_cover_image_id_cover_image",
        "inventory_copy",
        "cover_image",
        ["primary_cover_image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_inventory_copy_primary_cover_image_id"),
        "inventory_copy",
        ["primary_cover_image_id"],
        unique=False,
    )

    op.add_column(
        "draft_import",
        sa.Column("primary_cover_image_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_draft_import_primary_cover_image_id_cover_image",
        "draft_import",
        "cover_image",
        ["primary_cover_image_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_draft_import_primary_cover_image_id"),
        "draft_import",
        ["primary_cover_image_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_draft_import_primary_cover_image_id"),
        table_name="draft_import",
    )
    op.drop_constraint(
        "fk_draft_import_primary_cover_image_id_cover_image",
        "draft_import",
        type_="foreignkey",
    )
    op.drop_column("draft_import", "primary_cover_image_id")

    op.drop_index(
        op.f("ix_inventory_copy_primary_cover_image_id"),
        table_name="inventory_copy",
    )
    op.drop_constraint(
        "fk_inventory_copy_primary_cover_image_id_cover_image",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_column("inventory_copy", "primary_cover_image_id")
