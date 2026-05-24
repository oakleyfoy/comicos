"""Add OCR batch orchestration persistence.

Revision ID: 20260523_0031
Revises: 20260523_0030
Create Date: 2026-06-08 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0031"
down_revision: str | None = "20260523_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("pending_count", sa.Integer(), nullable=False),
        sa.Column("running_count", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("batch_options_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_key"),
    )
    op.create_index(op.f("ix_ocr_batch_batch_key"), "ocr_batch", ["batch_key"], unique=True)
    op.create_index(op.f("ix_ocr_batch_status"), "ocr_batch", ["status"], unique=False)
    op.create_index(op.f("ix_ocr_batch_created_by"), "ocr_batch", ["created_by"], unique=False)
    op.create_index(
        op.f("ix_ocr_batch_extraction_version"),
        "ocr_batch",
        ["extraction_version"],
        unique=False,
    )

    op.create_table(
        "ocr_batch_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["ocr_batch.id"]),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "cover_image_id", name="uq_ocr_batch_item_batch_cover"),
    )
    op.create_index(op.f("ix_ocr_batch_item_batch_id"), "ocr_batch_item", ["batch_id"], unique=False)
    op.create_index(
        op.f("ix_ocr_batch_item_cover_image_id"),
        "ocr_batch_item",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ocr_batch_item_status"), "ocr_batch_item", ["status"], unique=False)
    op.create_index(op.f("ix_ocr_batch_item_job_id"), "ocr_batch_item", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_batch_item_job_id"), table_name="ocr_batch_item")
    op.drop_index(op.f("ix_ocr_batch_item_status"), table_name="ocr_batch_item")
    op.drop_index(op.f("ix_ocr_batch_item_cover_image_id"), table_name="ocr_batch_item")
    op.drop_index(op.f("ix_ocr_batch_item_batch_id"), table_name="ocr_batch_item")
    op.drop_table("ocr_batch_item")

    op.drop_index(op.f("ix_ocr_batch_extraction_version"), table_name="ocr_batch")
    op.drop_index(op.f("ix_ocr_batch_created_by"), table_name="ocr_batch")
    op.drop_index(op.f("ix_ocr_batch_status"), table_name="ocr_batch")
    op.drop_index(op.f("ix_ocr_batch_batch_key"), table_name="ocr_batch")
    op.drop_table("ocr_batch")
