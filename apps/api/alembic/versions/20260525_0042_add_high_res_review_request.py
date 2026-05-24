"""Add high-resolution review request ledger (P34-03 Epson / flatbed workflow).

Revision ID: 20260525_0042
Revises: 20260525_0041
Create Date: 2026-05-25 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0042"
down_revision: str | None = "20260525_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "high_res_review_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("source_cover_image_id", sa.Integer(), nullable=True),
        sa.Column("source_scan_session_item_id", sa.Integer(), nullable=True),
        sa.Column("source_ocr_quality_analysis_id", sa.Integer(), nullable=True),
        sa.Column("source_inventory_risk_type", sa.String(length=80), nullable=True),
        sa.Column("source_action_center_category", sa.String(length=80), nullable=True),
        sa.Column("attach_scan_session_id", sa.Integer(), nullable=True),
        sa.Column("attach_scan_session_item_id", sa.Integer(), nullable=True),
        sa.Column("high_res_cover_image_id", sa.Integer(), nullable=True),
        sa.Column("request_reason", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.String(length=12), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["attach_scan_session_id"], ["scan_session.id"]),
        sa.ForeignKeyConstraint(["attach_scan_session_item_id"], ["scan_session_item.id"]),
        sa.ForeignKeyConstraint(["high_res_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["source_ocr_quality_analysis_id"], ["cover_image_ocr_quality_analysis.id"]),
        sa.ForeignKeyConstraint(["source_scan_session_item_id"], ["scan_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_high_res_review_request_inventory_copy_id"),
        "high_res_review_request",
        ["inventory_copy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_owner_user_id"),
        "high_res_review_request",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_status"),
        "high_res_review_request",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_priority"),
        "high_res_review_request",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_request_reason"),
        "high_res_review_request",
        ["request_reason"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_source_cover_image_id"),
        "high_res_review_request",
        ["source_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_source_scan_session_item_id"),
        "high_res_review_request",
        ["source_scan_session_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_source_ocr_quality_analysis_id"),
        "high_res_review_request",
        ["source_ocr_quality_analysis_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_attach_scan_session_id"),
        "high_res_review_request",
        ["attach_scan_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_attach_scan_session_item_id"),
        "high_res_review_request",
        ["attach_scan_session_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_high_res_review_request_high_res_cover_image_id"),
        "high_res_review_request",
        ["high_res_cover_image_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("high_res_review_request")
