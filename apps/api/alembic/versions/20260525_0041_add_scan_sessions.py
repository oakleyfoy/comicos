"""Add scan session orchestration tables (P34-01).

Revision ID: 20260525_0041
Revises: 20260524_0040
Create Date: 2026-05-25 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0041"
down_revision: str | None = "20260524_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scan_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("session_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scanner_profile", sa.String(length=120), nullable=True),
        sa.Column("source_device", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("skipped_items", sa.Integer(), nullable=False),
        sa.Column("session_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scan_session_owner_user_id"), "scan_session", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_scan_session_session_type"), "scan_session", ["session_type"], unique=False)
    op.create_index(op.f("ix_scan_session_status"), "scan_session", ["status"], unique=False)

    op.create_table(
        "scan_session_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_session_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("cover_image_id", sa.Integer(), nullable=True),
        sa.Column("source_filename", sa.String(length=510), nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("ingest_status", sa.String(length=40), nullable=False),
        sa.Column("ingest_error", sa.Text(), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["scan_session_id"], ["scan_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_session_id", "sequence_index", name="uq_scan_session_item_session_sequence_idx"),
    )
    op.create_index(op.f("ix_scan_session_item_scan_session_id"), "scan_session_item", ["scan_session_id"], unique=False)
    op.create_index(op.f("ix_scan_session_item_sequence_index"), "scan_session_item", ["sequence_index"], unique=False)
    op.create_index(op.f("ix_scan_session_item_ingest_status"), "scan_session_item", ["ingest_status"], unique=False)
    op.create_index(
        op.f("ix_scan_session_item_inventory_copy_id"),
        "scan_session_item",
        ["inventory_copy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scan_session_item_cover_image_id"),
        "scan_session_item",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scan_session_item_image_sha256"),
        "scan_session_item",
        ["image_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scan_session_item_image_sha256"), table_name="scan_session_item")
    op.drop_index(op.f("ix_scan_session_item_cover_image_id"), table_name="scan_session_item")
    op.drop_index(op.f("ix_scan_session_item_inventory_copy_id"), table_name="scan_session_item")
    op.drop_index(op.f("ix_scan_session_item_ingest_status"), table_name="scan_session_item")
    op.drop_index(op.f("ix_scan_session_item_sequence_index"), table_name="scan_session_item")
    op.drop_index(op.f("ix_scan_session_item_scan_session_id"), table_name="scan_session_item")
    op.drop_table("scan_session_item")

    op.drop_index(op.f("ix_scan_session_status"), table_name="scan_session")
    op.drop_index(op.f("ix_scan_session_session_type"), table_name="scan_session")
    op.drop_index(op.f("ix_scan_session_owner_user_id"), table_name="scan_session")
    op.drop_table("scan_session")
