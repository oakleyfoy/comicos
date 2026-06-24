"""P100 barcode companion image pairs with cover upload.

Revision ID: 20260627_0100
Revises: 20260626_0300
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260627_0100"
down_revision = "20260626_0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_image",
        sa.Column("image_role", sa.String(length=16), nullable=False, server_default="cover"),
    )
    op.add_column(
        "photo_import_image",
        sa.Column("pair_cover_image_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_photo_import_image_pair_cover",
        "photo_import_image",
        "photo_import_image",
        ["pair_cover_image_id"],
        ["id"],
    )
    op.create_index(
        "ix_photo_import_image_pair_cover",
        "photo_import_image",
        ["pair_cover_image_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_photo_import_image_pair_cover", table_name="photo_import_image")
    op.drop_constraint("fk_photo_import_image_pair_cover", "photo_import_image", type_="foreignkey")
    op.drop_column("photo_import_image", "pair_cover_image_id")
    op.drop_column("photo_import_image", "image_role")
