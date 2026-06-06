"""add P72 grading operations queue and batches

Revision ID: 20260607_0234
Revises: 20260606_0233
Create Date: 2026-06-07 02:34:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0234"
down_revision = "20260606_0233"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p72_grading_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("batch_name", sa.String(length=160), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=True),
        sa.Column("book_count", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("grader_received_date", sa.Date(), nullable=True),
        sa.Column("estimated_completion_date", sa.Date(), nullable=True),
        sa.Column("actual_completion_date", sa.Date(), nullable=True),
        sa.Column("turnaround_days", sa.Integer(), nullable=True),
        sa.Column("batch_status", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p72_grading_batch_owner_created", "p72_grading_batch", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "p72_grading_queue_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("p72_grading_batch_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("publisher", sa.String(length=80), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("submission_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("estimated_completion_date", sa.Date(), nullable=True),
        sa.Column("actual_completion_date", sa.Date(), nullable=True),
        sa.Column("turnaround_days", sa.Integer(), nullable=True),
        sa.Column("estimated_grading_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_grade", sa.String(length=32), nullable=True),
        sa.Column("certification_number", sa.String(length=64), nullable=True),
        sa.Column("slab_notes", sa.Text(), nullable=True),
        sa.Column("final_grading_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("search_blob", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["p72_grading_batch_id"], ["p72_grading_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p72_grading_queue_owner_status", "p72_grading_queue_entry", ["owner_user_id", "status", "id"])
    op.create_index("ix_p72_grading_queue_batch", "p72_grading_queue_entry", ["p72_grading_batch_id", "status", "id"])

    op.create_table(
        "p72_grading_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("queue_entry_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("prior_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["queue_entry_id"], ["p72_grading_queue_entry.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p72_grading_audit_queue_created", "p72_grading_audit_log", ["queue_entry_id", "created_at", "id"])

    op.create_table(
        "p72_inventory_grading_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("queue_entry_id", sa.Integer(), nullable=True),
        sa.Column("actual_grade", sa.String(length=32), nullable=False),
        sa.Column("certification_number", sa.String(length=64), nullable=True),
        sa.Column("slab_notes", sa.Text(), nullable=True),
        sa.Column("final_grading_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["queue_entry_id"], ["p72_grading_queue_entry.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p72_inv_grading_hist_copy",
        "p72_inventory_grading_history",
        ["inventory_copy_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p72_inv_grading_hist_copy", table_name="p72_inventory_grading_history")
    op.drop_table("p72_inventory_grading_history")
    op.drop_index("ix_p72_grading_audit_queue_created", table_name="p72_grading_audit_log")
    op.drop_table("p72_grading_audit_log")
    op.drop_index("ix_p72_grading_queue_batch", table_name="p72_grading_queue_entry")
    op.drop_index("ix_p72_grading_queue_owner_status", table_name="p72_grading_queue_entry")
    op.drop_table("p72_grading_queue_entry")
    op.drop_index("ix_p72_grading_batch_owner_created", table_name="p72_grading_batch")
    op.drop_table("p72_grading_batch")
