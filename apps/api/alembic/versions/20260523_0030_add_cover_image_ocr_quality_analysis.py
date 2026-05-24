"""Add cover image OCR quality analysis persistence.

Revision ID: 20260523_0030
Revises: 20260523_0029
Create Date: 2026-06-07 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0030"
down_revision: str | None = "20260523_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_ocr_quality_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("source_ocr_result_id", sa.Integer(), nullable=True),
        sa.Column("quality_type", sa.String(length=30), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["source_ocr_result_id"], ["cover_image_ocr_result.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cover_image_id",
            "quality_type",
            "extraction_version",
            name="uq_cover_image_ocr_quality_analysis_signature",
        ),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_quality_analysis_cover_image_id"),
        "cover_image_ocr_quality_analysis",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_quality_analysis_source_ocr_result_id"),
        "cover_image_ocr_quality_analysis",
        ["source_ocr_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_quality_analysis_quality_type"),
        "cover_image_ocr_quality_analysis",
        ["quality_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_quality_analysis_severity"),
        "cover_image_ocr_quality_analysis",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_quality_analysis_extraction_version"),
        "cover_image_ocr_quality_analysis",
        ["extraction_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_quality_analysis_extraction_version"),
        table_name="cover_image_ocr_quality_analysis",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_quality_analysis_severity"),
        table_name="cover_image_ocr_quality_analysis",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_quality_analysis_quality_type"),
        table_name="cover_image_ocr_quality_analysis",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_quality_analysis_source_ocr_result_id"),
        table_name="cover_image_ocr_quality_analysis",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_quality_analysis_cover_image_id"),
        table_name="cover_image_ocr_quality_analysis",
    )
    op.drop_table("cover_image_ocr_quality_analysis")
