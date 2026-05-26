"""P37-06 grading recommendation registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0066"
down_revision: str | None = "20260526_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("recommended_action", sa.String(length=24), nullable=False),
        sa.Column("recommended_grader", sa.String(length=16), nullable=True),
        sa.Column("recommended_grade_target", sa.String(length=32), nullable=True),
        sa.Column("expected_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("liquidity_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("estimated_net_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_total_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("recommendation_status", sa.String(length=16), nullable=False),
        sa.Column("rationale_summary", sa.Text(), nullable=False),
        sa.Column("warning_flags_json", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_recommendation_owner_replay"),
    )
    op.create_index(
        "ix_grading_recommendation_owner_status",
        "grading_recommendation",
        ["owner_user_id", "recommendation_status", "recommended_action", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_recommendation_owner_strength",
        "grading_recommendation",
        ["owner_user_id", "recommendation_strength", "risk_level", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_recommendation_scope_date",
        "grading_recommendation",
        ["owner_user_id", "grading_candidate_id", "inventory_item_id", "canonical_comic_issue_id", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "grading_recommendation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_recommendation_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_recommendation_id"], ["grading_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_recommendation_evidence_recommendation_created",
        "grading_recommendation_evidence",
        ["grading_recommendation_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "grading_recommendation_scenario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_recommendation_id", sa.Integer(), nullable=False),
        sa.Column("scenario_name", sa.String(length=16), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=True),
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("confidence_modifier", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_recommendation_id"], ["grading_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_recommendation_scenario_recommendation_name",
        "grading_recommendation_scenario",
        ["grading_recommendation_id", "scenario_name", "id"],
        unique=False,
    )

    op.create_table(
        "grading_recommendation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("recommended_action", sa.String(length=24), nullable=False),
        sa.Column("recommended_grader", sa.String(length=16), nullable=True),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "recommended_action",
            "recommended_grader",
            "snapshot_date",
            "checksum",
            name="uq_grading_recommendation_history_signature",
        ),
    )
    op.create_index(
        "ix_grading_recommendation_history_scope_date",
        "grading_recommendation_history",
        ["owner_user_id", "grading_candidate_id", "inventory_item_id", "snapshot_date", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_recommendation_history_scope_date", table_name="grading_recommendation_history")
    op.drop_table("grading_recommendation_history")
    op.drop_index("ix_grading_recommendation_scenario_recommendation_name", table_name="grading_recommendation_scenario")
    op.drop_table("grading_recommendation_scenario")
    op.drop_index("ix_grading_recommendation_evidence_recommendation_created", table_name="grading_recommendation_evidence")
    op.drop_table("grading_recommendation_evidence")
    op.drop_index("ix_grading_recommendation_scope_date", table_name="grading_recommendation")
    op.drop_index("ix_grading_recommendation_owner_strength", table_name="grading_recommendation")
    op.drop_index("ix_grading_recommendation_owner_status", table_name="grading_recommendation")
    op.drop_table("grading_recommendation")
