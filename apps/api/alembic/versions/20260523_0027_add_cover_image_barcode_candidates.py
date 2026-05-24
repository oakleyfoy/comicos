"""Add cover image barcode candidate persistence.

Revision ID: 20260523_0027
Revises: 20260523_0026
Create Date: 2026-06-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0027"
down_revision: str | None = "20260523_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_barcode_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("source_ocr_result_id", sa.Integer(), nullable=True),
        sa.Column("source_ocr_candidate_id", sa.Integer(), nullable=True),
        sa.Column("raw_barcode_value", sa.Text(), nullable=False),
        sa.Column("normalized_upc_value", sa.String(length=32), nullable=False),
        sa.Column("barcode_type", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("review_state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["source_ocr_result_id"], ["cover_image_ocr_result.id"]),
        sa.ForeignKeyConstraint(["source_ocr_candidate_id"], ["cover_image_ocr_candidate.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_cover_image_id"),
        "cover_image_barcode_candidate",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_source_ocr_result_id"),
        "cover_image_barcode_candidate",
        ["source_ocr_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_source_ocr_candidate_id"),
        "cover_image_barcode_candidate",
        ["source_ocr_candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_normalized_upc_value"),
        "cover_image_barcode_candidate",
        ["normalized_upc_value"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_barcode_type"),
        "cover_image_barcode_candidate",
        ["barcode_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_extraction_version"),
        "cover_image_barcode_candidate",
        ["extraction_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_review_state"),
        "cover_image_barcode_candidate",
        ["review_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_barcode_candidate_reviewed_by_user_id"),
        "cover_image_barcode_candidate",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_reviewed_by_user_id"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_review_state"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_extraction_version"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_barcode_type"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_normalized_upc_value"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_source_ocr_candidate_id"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_source_ocr_result_id"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_barcode_candidate_cover_image_id"),
        table_name="cover_image_barcode_candidate",
    )
    op.drop_table("cover_image_barcode_candidate")
