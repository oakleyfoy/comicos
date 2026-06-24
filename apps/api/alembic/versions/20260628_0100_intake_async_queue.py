"""Async intake queue: hands-free scan sessions, queued items, candidates, learned barcodes.

Revision ID: 20260628_0100
Revises: 20260627_0100
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_0100"
down_revision = "20260627_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_device", sa.String(length=128), nullable=True),
        sa.Column("scanned_count", sa.Integer(), nullable=False),
        sa.Column("acquisition_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.create_index("ix_intake_session_user_id", "intake_session", ["user_id"])
    op.create_index("ix_intake_session_token", "intake_session", ["session_token"], unique=True)

    op.create_table(
        "intake_session_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("raw_barcode", sa.String(length=64), nullable=True),
        sa.Column("normalized_barcode", sa.String(length=64), nullable=True),
        sa.Column("base_upc", sa.String(length=16), nullable=True),
        sa.Column("extension", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("match_source", sa.String(length=32), nullable=True),
        sa.Column("selected_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("selected_variant_id", sa.Integer(), nullable=True),
        sa.Column("matched_publisher", sa.String(length=256), nullable=True),
        sa.Column("matched_series", sa.String(length=512), nullable=True),
        sa.Column("matched_issue_number", sa.String(length=64), nullable=True),
        sa.Column("matched_year", sa.String(length=16), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("acquisition_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["intake_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intake_item_session", "intake_session_item", ["session_id", "id"])
    op.create_index("ix_intake_item_status", "intake_session_item", ["status", "id"])
    op.create_index("ix_intake_item_norm_barcode", "intake_session_item", ["normalized_barcode"])
    op.create_index("ix_intake_item_catalog_issue", "intake_session_item", ["selected_catalog_issue_id"])

    op.create_table(
        "intake_item_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(length=256), nullable=True),
        sa.Column("series", sa.String(length=512), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["intake_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intake_candidate_item", "intake_item_candidate", ["item_id", "rank"])

    op.create_table(
        "comic_issue_barcodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("normalized_barcode", sa.String(length=64), nullable=False),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("times_seen", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_barcode"),
    )
    op.create_index(
        "ix_comic_issue_barcodes_norm", "comic_issue_barcodes", ["normalized_barcode"], unique=True
    )
    op.create_index("ix_comic_issue_barcodes_issue", "comic_issue_barcodes", ["catalog_issue_id"])


def downgrade() -> None:
    op.drop_index("ix_comic_issue_barcodes_issue", table_name="comic_issue_barcodes")
    op.drop_index("ix_comic_issue_barcodes_norm", table_name="comic_issue_barcodes")
    op.drop_table("comic_issue_barcodes")
    op.drop_index("ix_intake_candidate_item", table_name="intake_item_candidate")
    op.drop_table("intake_item_candidate")
    op.drop_index("ix_intake_item_catalog_issue", table_name="intake_session_item")
    op.drop_index("ix_intake_item_norm_barcode", table_name="intake_session_item")
    op.drop_index("ix_intake_item_status", table_name="intake_session_item")
    op.drop_index("ix_intake_item_session", table_name="intake_session_item")
    op.drop_table("intake_session_item")
    op.drop_index("ix_intake_session_token", table_name="intake_session")
    op.drop_index("ix_intake_session_user_id", table_name="intake_session")
    op.drop_table("intake_session")
