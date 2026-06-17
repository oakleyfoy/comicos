"""P100-12 photo import AI fields and candidate matched_on."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260621_0212"
down_revision = "20260620_0211"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_subtitle_guess", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_variant_guess", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_visible_title_text", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_visible_issue_text", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_visible_publisher_text", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_visible_character_text", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_uncertainty_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "photo_import_detected_book",
        sa.Column("ai_alternate_titles", sa.JSON(), nullable=True),
    )
    op.add_column(
        "photo_import_candidate",
        sa.Column("matched_on", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("photo_import_candidate", "matched_on")
    op.drop_column("photo_import_detected_book", "ai_alternate_titles")
    op.drop_column("photo_import_detected_book", "ai_uncertainty_reason")
    op.drop_column("photo_import_detected_book", "ai_visible_character_text")
    op.drop_column("photo_import_detected_book", "ai_visible_publisher_text")
    op.drop_column("photo_import_detected_book", "ai_visible_issue_text")
    op.drop_column("photo_import_detected_book", "ai_visible_title_text")
    op.drop_column("photo_import_detected_book", "ai_variant_guess")
    op.drop_column("photo_import_detected_book", "ai_subtitle_guess")
