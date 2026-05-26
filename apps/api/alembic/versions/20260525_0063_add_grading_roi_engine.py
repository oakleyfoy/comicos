"""P37-03 grading ROI engine registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0063"
down_revision: str | None = "20260525_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_roi_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("raw_fmv_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("graded_fmv_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("grading_fee_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("shipping_cost_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("insurance_cost_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_turnaround_days", sa.Integer(), nullable=True),
        sa.Column("estimated_total_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_spread_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_net_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_roi_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("liquidity_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("break_even_grade", sa.String(length=32), nullable=True),
        sa.Column("roi_status", sa.String(length=24), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("generation_params_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_roi_snapshot_owner_replay"),
    )
    op.create_index(
        "ix_grading_roi_snapshot_owner_inventory_date",
        "grading_roi_snapshot",
        ["owner_user_id", "inventory_item_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_roi_snapshot_owner_status",
        "grading_roi_snapshot",
        ["owner_user_id", "roi_status", "confidence_level", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_roi_snapshot_candidate_target",
        "grading_roi_snapshot",
        ["grading_candidate_id", "target_grader", "target_grade", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "grading_roi_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_roi_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_roi_snapshot_id"], ["grading_roi_snapshot.id"]),
    )
    op.create_index(
        "ix_grading_roi_evidence_snapshot_created",
        "grading_roi_evidence",
        ["grading_roi_snapshot_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_roi_scenario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_roi_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("scenario_name", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_roi_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("liquidity_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_roi_snapshot_id"], ["grading_roi_snapshot.id"]),
    )
    op.create_index(
        "ix_grading_roi_scenario_snapshot_name",
        "grading_roi_scenario",
        ["grading_roi_snapshot_id", "scenario_name", "id"],
        unique=False,
    )

    op.create_table(
        "grading_roi_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("target_grader", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("roi_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("liquidity_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_roi_history_signature",
        ),
    )
    op.create_index(
        "ix_grading_roi_history_issue_target_date",
        "grading_roi_history",
        [
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_roi_history_issue_target_date", table_name="grading_roi_history")
    op.drop_table("grading_roi_history")
    op.drop_index("ix_grading_roi_scenario_snapshot_name", table_name="grading_roi_scenario")
    op.drop_table("grading_roi_scenario")
    op.drop_index("ix_grading_roi_evidence_snapshot_created", table_name="grading_roi_evidence")
    op.drop_table("grading_roi_evidence")
    op.drop_index("ix_grading_roi_snapshot_candidate_target", table_name="grading_roi_snapshot")
    op.drop_index("ix_grading_roi_snapshot_owner_status", table_name="grading_roi_snapshot")
    op.drop_index("ix_grading_roi_snapshot_owner_inventory_date", table_name="grading_roi_snapshot")
    op.drop_table("grading_roi_snapshot")
