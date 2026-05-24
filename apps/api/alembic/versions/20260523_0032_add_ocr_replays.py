"""Add OCR replay regression persistence.

Revision ID: 20260523_0032
Revises: 20260523_0031
Create Date: 2026-06-08 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0032"
down_revision: str | None = "20260523_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_replay_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_type", sa.String(length=40), nullable=False),
        sa.Column("extraction_version_from", sa.String(length=255), nullable=False),
        sa.Column("extraction_version_to", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("changed_items", sa.Integer(), nullable=False),
        sa.Column("unchanged_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ocr_replay_run_replay_type"), "ocr_replay_run", ["replay_type"], unique=False)
    op.create_index(op.f("ix_ocr_replay_run_status"), "ocr_replay_run", ["status"], unique=False)
    op.create_index(op.f("ix_ocr_replay_run_created_by"), "ocr_replay_run", ["created_by"], unique=False)

    op.create_table(
        "ocr_replay_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("previous_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("replay_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("diff_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["replay_run_id"], ["ocr_replay_run.id"]),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "cover_image_id", name="uq_ocr_replay_item_run_cover"),
    )
    op.create_index(op.f("ix_ocr_replay_item_replay_run_id"), "ocr_replay_item", ["replay_run_id"], unique=False)
    op.create_index(
        op.f("ix_ocr_replay_item_cover_image_id"),
        "ocr_replay_item",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ocr_replay_item_status"), "ocr_replay_item", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_replay_item_status"), table_name="ocr_replay_item")
    op.drop_index(op.f("ix_ocr_replay_item_cover_image_id"), table_name="ocr_replay_item")
    op.drop_index(op.f("ix_ocr_replay_item_replay_run_id"), table_name="ocr_replay_item")
    op.drop_table("ocr_replay_item")

    op.drop_index(op.f("ix_ocr_replay_run_created_by"), table_name="ocr_replay_run")
    op.drop_index(op.f("ix_ocr_replay_run_status"), table_name="ocr_replay_run")
    op.drop_index(op.f("ix_ocr_replay_run_replay_type"), table_name="ocr_replay_run")
    op.drop_table("ocr_replay_run")
"""Add OCR replay regression persistence.

Revision ID: 20260523_0032
Revises: 20260523_0031
Create Date: 2026-06-08 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0032"
down_revision: str | None = "20260523_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_replay_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_type", sa.String(length=40), nullable=False),
        sa.Column("extraction_version_from", sa.String(length=255), nullable=False),
        sa.Column("extraction_version_to", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("changed_items", sa.Integer(), nullable=False),
        sa.Column("unchanged_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ocr_replay_run_replay_type"), "ocr_replay_run", ["replay_type"], unique=False)
    op.create_index(op.f("ix_ocr_replay_run_status"), "ocr_replay_run", ["status"], unique=False)
    op.create_index(op.f("ix_ocr_replay_run_created_by"), "ocr_replay_run", ["created_by"], unique=False)

    op.create_table(
        "ocr_replay_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("previous_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("replay_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("diff_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["replay_run_id"], ["ocr_replay_run.id"]),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "cover_image_id", name="uq_ocr_replay_item_run_cover"),
    )
    op.create_index(op.f("ix_ocr_replay_item_replay_run_id"), "ocr_replay_item", ["replay_run_id"], unique=False)
    op.create_index(
        op.f("ix_ocr_replay_item_cover_image_id"),
        "ocr_replay_item",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ocr_replay_item_status"), "ocr_replay_item", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_replay_item_status"), table_name="ocr_replay_item")
    op.drop_index(op.f("ix_ocr_replay_item_cover_image_id"), table_name="ocr_replay_item")
    op.drop_index(op.f("ix_ocr_replay_item_replay_run_id"), table_name="ocr_replay_item")
    op.drop_table("ocr_replay_item")

    op.drop_index(op.f("ix_ocr_replay_run_created_by"), table_name="ocr_replay_run")
    op.drop_index(op.f("ix_ocr_replay_run_status"), table_name="ocr_replay_run")
    op.drop_index(op.f("ix_ocr_replay_run_replay_type"), table_name="ocr_replay_run")
    op.drop_table("ocr_replay_run")
