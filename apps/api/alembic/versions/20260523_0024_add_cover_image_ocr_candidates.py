"""Add cover image OCR candidates.

Revision ID: 20260523_0024
Revises: 20260523_0023
Create Date: 2026-05-24 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0024"
down_revision: str | None = "20260523_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_ocr_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("ocr_result_id", sa.Integer(), nullable=False),
        sa.Column("candidate_type", sa.String(length=50), nullable=False),
        sa.Column("raw_candidate_text", sa.Text(), nullable=False),
        sa.Column("normalized_candidate_text", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("extraction_source", sa.String(length=50), nullable=False),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["ocr_result_id"], ["cover_image_ocr_result.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_cover_image_id"),
        "cover_image_ocr_candidate",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_ocr_result_id"),
        "cover_image_ocr_candidate",
        ["ocr_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_candidate_type"),
        "cover_image_ocr_candidate",
        ["candidate_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_extraction_source"),
        "cover_image_ocr_candidate",
        ["extraction_source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_extraction_version"),
        "cover_image_ocr_candidate",
        ["extraction_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_extraction_version"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_extraction_source"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_candidate_type"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_ocr_result_id"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_cover_image_id"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_table("cover_image_ocr_candidate")
