"""P100 multi-book: detection_index + catalog match fields on vision reads."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260625_0200"
down_revision = "20260625_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_vision_read",
        sa.Column("detection_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("photo_import_vision_read", sa.Column("catalog_issue_id", sa.Integer(), nullable=True))
    op.add_column("photo_import_vision_read", sa.Column("catalog_variant_id", sa.Integer(), nullable=True))
    op.add_column("photo_import_vision_read", sa.Column("catalog_cover_url", sa.Text(), nullable=True))
    op.add_column("photo_import_vision_read", sa.Column("match_confidence", sa.Float(), nullable=True))
    op.add_column("photo_import_vision_read", sa.Column("match_method", sa.String(length=16), nullable=True))
    op.create_index(
        "ix_photo_import_vision_read_catalog_issue_id",
        "photo_import_vision_read",
        ["catalog_issue_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_photo_import_vision_read_catalog_issue_id", table_name="photo_import_vision_read")
    op.drop_column("photo_import_vision_read", "match_method")
    op.drop_column("photo_import_vision_read", "match_confidence")
    op.drop_column("photo_import_vision_read", "catalog_cover_url")
    op.drop_column("photo_import_vision_read", "catalog_variant_id")
    op.drop_column("photo_import_vision_read", "catalog_issue_id")
    op.drop_column("photo_import_vision_read", "detection_index")
