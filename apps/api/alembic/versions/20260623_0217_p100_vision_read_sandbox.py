"""P100-24 vision read sandbox table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260623_0217"
down_revision = "20260623_0216"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "photo_import_vision_read",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=True),
        sa.Column("series", sa.String(length=512), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("issue_title", sa.String(length=512), nullable=True),
        sa.Column("variant_description", sa.String(length=512), nullable=True),
        sa.Column("year", sa.String(length=16), nullable=True),
        sa.Column("cover_date", sa.String(length=32), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("raw_response_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("feedback_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["photo_import_session.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["photo_import_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_import_vision_read_session_id", "photo_import_vision_read", ["session_id"])
    op.create_index("ix_photo_import_vision_read_image_id", "photo_import_vision_read", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_photo_import_vision_read_image_id", table_name="photo_import_vision_read")
    op.drop_index("ix_photo_import_vision_read_session_id", table_name="photo_import_vision_read")
    op.drop_table("photo_import_vision_read")
