"""Add OCR candidate human review fields.

Revision ID: 20260523_0025
Revises: 20260523_0024
Create Date: 2026-06-07 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0025"
down_revision: str | None = "20260523_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image_ocr_candidate",
        sa.Column("review_status", sa.String(length=20), server_default="pending", nullable=False),
    )
    op.add_column(
        "cover_image_ocr_candidate",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_candidate",
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cover_image_ocr_candidate",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_cover_image_ocr_candidate_reviewed_by_user_id_user"),
        "cover_image_ocr_candidate",
        "user",
        ["reviewed_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_review_status"),
        "cover_image_ocr_candidate",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_candidate_reviewed_by_user_id"),
        "cover_image_ocr_candidate",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_candidate_reviewed_by_user_id"),
        table_name="cover_image_ocr_candidate",
    )
    op.drop_index(op.f("ix_cover_image_ocr_candidate_review_status"), table_name="cover_image_ocr_candidate")
    op.drop_constraint(
        op.f("fk_cover_image_ocr_candidate_reviewed_by_user_id_user"),
        "cover_image_ocr_candidate",
        type_="foreignkey",
    )
    op.drop_column("cover_image_ocr_candidate", "review_notes")
    op.drop_column("cover_image_ocr_candidate", "reviewed_by_user_id")
    op.drop_column("cover_image_ocr_candidate", "reviewed_at")
    op.drop_column("cover_image_ocr_candidate", "review_status")
