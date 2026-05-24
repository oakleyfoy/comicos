"""Add cover image OCR regions.

Revision ID: 20260523_0023
Revises: 20260523_0022
Create Date: 2026-05-24 21:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0023"
down_revision: str | None = "20260523_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_ocr_region",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("derivative_id", sa.Integer(), nullable=True),
        sa.Column("region_type", sa.String(length=50), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["derivative_id"], ["cover_image_derivative.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cover_image_id",
            "region_type",
            name="uq_cover_image_ocr_region_cover_type",
        ),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_region_cover_image_id"),
        "cover_image_ocr_region",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_region_derivative_id"),
        "cover_image_ocr_region",
        ["derivative_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_region_region_type"),
        "cover_image_ocr_region",
        ["region_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_region_sha256_hash"),
        "cover_image_ocr_region",
        ["sha256_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_region_extraction_version"),
        "cover_image_ocr_region",
        ["extraction_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_region_extraction_version"),
        table_name="cover_image_ocr_region",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_region_sha256_hash"),
        table_name="cover_image_ocr_region",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_region_region_type"),
        table_name="cover_image_ocr_region",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_region_derivative_id"),
        table_name="cover_image_ocr_region",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_region_cover_image_id"),
        table_name="cover_image_ocr_region",
    )
    op.drop_table("cover_image_ocr_region")
