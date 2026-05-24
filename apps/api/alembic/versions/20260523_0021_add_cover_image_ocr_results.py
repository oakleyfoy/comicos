"""Add cover image OCR results.

Revision ID: 20260523_0021
Revises: 20260523_0020
Create Date: 2026-05-24 18:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0021"
down_revision: str | None = "20260523_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_ocr_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("ocr_engine", sa.String(length=50), nullable=False),
        sa.Column("ocr_engine_version", sa.String(length=255), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_result_cover_image_id"),
        "cover_image_ocr_result",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_result_processing_status"),
        "cover_image_ocr_result",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_result_processing_status"),
        table_name="cover_image_ocr_result",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_result_cover_image_id"),
        table_name="cover_image_ocr_result",
    )
    op.drop_table("cover_image_ocr_result")
