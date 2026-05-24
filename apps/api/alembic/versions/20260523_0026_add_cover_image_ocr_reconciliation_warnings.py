"""Add OCR reconciliation warning rows.

Revision ID: 20260523_0026
Revises: 20260523_0025
Create Date: 2026-06-07 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0026"
down_revision: str | None = "20260523_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_ocr_reconciliation_warning",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("ocr_candidate_id", sa.Integer(), nullable=True),
        sa.Column("warning_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("current_metadata_value", sa.Text(), nullable=True),
        sa.Column("candidate_value", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["ocr_candidate_id"], ["cover_image_ocr_candidate.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_cover_image_id"),
        "cover_image_ocr_reconciliation_warning",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_inventory_copy_id"),
        "cover_image_ocr_reconciliation_warning",
        ["inventory_copy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_ocr_candidate_id"),
        "cover_image_ocr_reconciliation_warning",
        ["ocr_candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_warning_type"),
        "cover_image_ocr_reconciliation_warning",
        ["warning_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_severity"),
        "cover_image_ocr_reconciliation_warning",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_status"),
        "cover_image_ocr_reconciliation_warning",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_resolved_by_user_id"),
        "cover_image_ocr_reconciliation_warning",
        ["resolved_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_resolved_by_user_id"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_status"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_severity"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_warning_type"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_ocr_candidate_id"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_inventory_copy_id"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_index(
        op.f("ix_cover_image_ocr_reconciliation_warning_cover_image_id"),
        table_name="cover_image_ocr_reconciliation_warning",
    )
    op.drop_table("cover_image_ocr_reconciliation_warning")
