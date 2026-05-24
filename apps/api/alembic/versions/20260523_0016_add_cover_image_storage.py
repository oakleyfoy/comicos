"""Add cover_image storage foundation.

Revision ID: 20260523_0016
Revises: 20260523_0015
Create Date: 2026-05-24 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0016"
down_revision: str | None = "20260523_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("canonical_series_id", sa.Integer(), nullable=True),
        sa.Column("draft_import_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=510), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_series_id"],
            ["canonical_series.id"],
        ),
        sa.ForeignKeyConstraint(
            ["draft_import_id"],
            ["draft_import.id"],
        ),
        sa.ForeignKeyConstraint(
            ["inventory_copy_id"],
            ["inventory_copy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_canonical_series_id"),
        "cover_image",
        ["canonical_series_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_draft_import_id"),
        "cover_image",
        ["draft_import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_inventory_copy_id"),
        "cover_image",
        ["inventory_copy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_sha256_hash"),
        "cover_image",
        ["sha256_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cover_image_sha256_hash"), table_name="cover_image")
    op.drop_index(op.f("ix_cover_image_inventory_copy_id"), table_name="cover_image")
    op.drop_index(op.f("ix_cover_image_draft_import_id"), table_name="cover_image")
    op.drop_index(op.f("ix_cover_image_canonical_series_id"), table_name="cover_image")
    op.drop_table("cover_image")
