"""Add deterministic cover image derivative table.

Revision ID: 20260523_0019
Revises: 20260523_0018
Create Date: 2026-05-24 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0019"
down_revision: str | None = "20260523_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_derivative",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("derivative_type", sa.String(length=20), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cover_image_id",
            "derivative_type",
            name="uq_cover_image_derivative_cover_type",
        ),
    )
    op.create_index(
        op.f("ix_cover_image_derivative_cover_image_id"),
        "cover_image_derivative",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_derivative_derivative_type"),
        "cover_image_derivative",
        ["derivative_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_derivative_sha256_hash"),
        "cover_image_derivative",
        ["sha256_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cover_image_derivative_sha256_hash"), table_name="cover_image_derivative")
    op.drop_index(
        op.f("ix_cover_image_derivative_derivative_type"),
        table_name="cover_image_derivative",
    )
    op.drop_index(
        op.f("ix_cover_image_derivative_cover_image_id"),
        table_name="cover_image_derivative",
    )
    op.drop_table("cover_image_derivative")
