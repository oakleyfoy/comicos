"""Add cover image fingerprint persistence.

Revision ID: 20260523_0028
Revises: 20260523_0027
Create Date: 2026-06-07 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0028"
down_revision: str | None = "20260523_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_fingerprint",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint_type", sa.String(length=20), nullable=False),
        sa.Column("fingerprint_value", sa.String(length=255), nullable=False),
        sa.Column("derivative_type", sa.String(length=20), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=True),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_fingerprint_cover_image_id"),
        "cover_image_fingerprint",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_fingerprint_fingerprint_type"),
        "cover_image_fingerprint",
        ["fingerprint_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_fingerprint_derivative_type"),
        "cover_image_fingerprint",
        ["derivative_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_fingerprint_extraction_version"),
        "cover_image_fingerprint",
        ["extraction_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_fingerprint_extraction_version"),
        table_name="cover_image_fingerprint",
    )
    op.drop_index(
        op.f("ix_cover_image_fingerprint_derivative_type"),
        table_name="cover_image_fingerprint",
    )
    op.drop_index(
        op.f("ix_cover_image_fingerprint_fingerprint_type"),
        table_name="cover_image_fingerprint",
    )
    op.drop_index(
        op.f("ix_cover_image_fingerprint_cover_image_id"),
        table_name="cover_image_fingerprint",
    )
    op.drop_table("cover_image_fingerprint")
