"""add P72 grading outcome analytics

Revision ID: 20260607_0235
Revises: 20260607_0234
Create Date: 2026-06-07 02:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0235"
down_revision = "20260607_0234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p72_grading_outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("queue_entry_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("publisher", sa.String(length=80), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("series", sa.String(length=160), nullable=False),
        sa.Column("era", sa.String(length=32), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("pressing_recommended", sa.String(length=16), nullable=False),
        sa.Column("was_pressed", sa.Boolean(), nullable=False),
        sa.Column("expected_grade", sa.String(length=16), nullable=False),
        sa.Column("actual_grade", sa.String(length=16), nullable=False),
        sa.Column("expected_roi_pct", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_roi_pct", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_profit", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_profit", sa.Numeric(12, 2), nullable=False),
        sa.Column("raw_fmv", sa.Numeric(12, 2), nullable=False),
        sa.Column("graded_value_estimate", sa.Numeric(12, 2), nullable=False),
        sa.Column("actual_grading_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("recommendation_accuracy", sa.String(length=16), nullable=False),
        sa.Column("queue_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["queue_entry_id"], ["p72_grading_queue_entry.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("queue_entry_id", name="uq_p72_grading_outcome_queue_entry"),
    )
    op.create_index(
        "ix_p72_grading_outcome_owner_recorded",
        "p72_grading_outcome",
        ["owner_user_id", "recorded_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p72_grading_outcome_owner_recorded", table_name="p72_grading_outcome")
    op.drop_table("p72_grading_outcome")
