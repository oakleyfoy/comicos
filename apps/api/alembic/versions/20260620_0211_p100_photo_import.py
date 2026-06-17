"""P100 photo import database tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0211"
down_revision = "20260619_0210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "photo_import_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_device", sa.String(length=128), nullable=True),
        sa.Column("confirmed_count", sa.Integer(), nullable=False),
        sa.Column("uploaded_photo_count", sa.Integer(), nullable=False),
        sa.Column("detected_book_count", sa.Integer(), nullable=False),
        sa.Column("acquisition_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["acquisition_id"], ["acquisitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.create_index("ix_photo_import_session_user_id", "photo_import_session", ["user_id"])
    op.create_index("ix_photo_import_session_status", "photo_import_session", ["status", "id"])

    op.create_table(
        "photo_import_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["photo_import_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_import_image_session_id", "photo_import_image", ["session_id", "id"])

    op.create_table(
        "photo_import_detected_book",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("crop_path", sa.String(length=1024), nullable=True),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_width", sa.Float(), nullable=False),
        sa.Column("bbox_height", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recognition_status", sa.String(length=32), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("selected_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("selected_variant_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_series", sa.String(length=512), nullable=True),
        sa.Column("ai_issue_number", sa.String(length=64), nullable=True),
        sa.Column("ai_publisher", sa.String(length=256), nullable=True),
        sa.Column("ai_variant_hint", sa.String(length=256), nullable=True),
        sa.Column("ai_cover_year", sa.String(length=16), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("raw_ai_response", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["photo_import_session.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["photo_import_image.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_import_detected_book_session", "photo_import_detected_book", ["session_id", "id"])

    op.create_table(
        "photo_import_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detected_book_id", sa.Integer(), nullable=False),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(length=256), nullable=True),
        sa.Column("series", sa.String(length=512), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("variant_name", sa.String(length=256), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("release_date", sa.String(length=32), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("match_reason", sa.String(length=512), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["detected_book_id"], ["photo_import_detected_book.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_photo_import_candidate_detected", "photo_import_candidate", ["detected_book_id", "rank"])


def downgrade() -> None:
    op.drop_index("ix_photo_import_candidate_detected", table_name="photo_import_candidate")
    op.drop_table("photo_import_candidate")
    op.drop_index("ix_photo_import_detected_book_session", table_name="photo_import_detected_book")
    op.drop_table("photo_import_detected_book")
    op.drop_index("ix_photo_import_image_session_id", table_name="photo_import_image")
    op.drop_table("photo_import_image")
    op.drop_index("ix_photo_import_session_status", table_name="photo_import_session")
    op.drop_index("ix_photo_import_session_user_id", table_name="photo_import_session")
    op.drop_table("photo_import_session")
