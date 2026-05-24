"""Add cover image OCR audit fields.

Revision ID: 20260523_0022
Revises: 20260523_0021
Create Date: 2026-05-24 20:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0022"
down_revision: str | None = "20260523_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("source_cover_image_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("source_thumb_derivative_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("source_medium_derivative_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("source_processing_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("normalization_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("replay_of_ocr_result_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_result",
        sa.Column("replay_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_result_replay_of_ocr_result_id"),
        "cover_image_ocr_result",
        ["replay_of_ocr_result_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_cover_image_ocr_result_replay_of_ocr_result_id",
        "cover_image_ocr_result",
        "cover_image_ocr_result",
        ["replay_of_ocr_result_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cover_image_ocr_result_replay_of_ocr_result_id",
        "cover_image_ocr_result",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_result_replay_of_ocr_result_id"),
        table_name="cover_image_ocr_result",
    )
    op.drop_column("cover_image_ocr_result", "replay_reason")
    op.drop_column("cover_image_ocr_result", "replay_of_ocr_result_id")
    op.drop_column("cover_image_ocr_result", "normalization_version")
    op.drop_column("cover_image_ocr_result", "source_processing_version")
    op.drop_column("cover_image_ocr_result", "source_medium_derivative_sha256")
    op.drop_column("cover_image_ocr_result", "source_thumb_derivative_sha256")
    op.drop_column("cover_image_ocr_result", "source_cover_image_sha256")
