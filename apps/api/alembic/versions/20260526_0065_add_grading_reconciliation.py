"""P37-05 grading reconciliation registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0065"
down_revision: str | None = "20260525_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_reconciliation_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_submission_item_id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("expected_grade", sa.String(length=32), nullable=True),
        sa.Column("final_grade", sa.String(length=32), nullable=True),
        sa.Column("expected_raw_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_graded_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("realized_graded_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("realized_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("roi_delta", sa.Numeric(18, 8), nullable=True),
        sa.Column("grading_accuracy_status", sa.String(length=24), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=24), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["grading_submission_item_id"], ["grading_submission_item.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "grading_submission_item_id",
            "checksum",
            name="uq_grading_reconciliation_item_checksum",
        ),
    )
    op.create_index(
        "ix_grading_reconciliation_record_owner_status",
        "grading_reconciliation_record",
        ["owner_user_id", "reconciliation_status", "grading_accuracy_status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_reconciliation_record_owner_created",
        "grading_reconciliation_record",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_reconciliation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_reconciliation_record_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_reconciliation_record_id"], ["grading_reconciliation_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_reconciliation_evidence_record_created",
        "grading_reconciliation_evidence",
        ["grading_reconciliation_record_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_reconciliation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("expected_grade", sa.String(length=32), nullable=True),
        sa.Column("actual_grade", sa.String(length=32), nullable=True),
        sa.Column("realized_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("roi_delta", sa.Numeric(18, 8), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "target_grader",
            "expected_grade",
            "actual_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_reconciliation_history_signature",
        ),
    )
    op.create_index(
        "ix_grading_reconciliation_history_owner_target_date",
        "grading_reconciliation_history",
        ["owner_user_id", "grading_candidate_id", "inventory_item_id", "target_grader", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "grader_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grader", sa.String(length=16), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=False),
        sa.Column("above_expectation_count", sa.Integer(), nullable=False),
        sa.Column("met_expectation_count", sa.Integer(), nullable=False),
        sa.Column("below_expectation_count", sa.Integer(), nullable=False),
        sa.Column("average_roi_delta", sa.Numeric(18, 8), nullable=True),
        sa.Column("average_turnaround_days", sa.Numeric(12, 2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "grader",
            "snapshot_date",
            "checksum",
            name="uq_grader_performance_snapshot_signature",
        ),
    )
    op.create_index(
        "ix_grader_performance_snapshot_owner_grader_date",
        "grader_performance_snapshot",
        ["owner_user_id", "grader", "snapshot_date", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grader_performance_snapshot_owner_grader_date", table_name="grader_performance_snapshot")
    op.drop_table("grader_performance_snapshot")
    op.drop_index("ix_grading_reconciliation_history_owner_target_date", table_name="grading_reconciliation_history")
    op.drop_table("grading_reconciliation_history")
    op.drop_index("ix_grading_reconciliation_evidence_record_created", table_name="grading_reconciliation_evidence")
    op.drop_table("grading_reconciliation_evidence")
    op.drop_index("ix_grading_reconciliation_record_owner_created", table_name="grading_reconciliation_record")
    op.drop_index("ix_grading_reconciliation_record_owner_status", table_name="grading_reconciliation_record")
    op.drop_table("grading_reconciliation_record")
