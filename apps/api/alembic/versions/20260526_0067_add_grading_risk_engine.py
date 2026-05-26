"""P37-07 grading risk engine tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0067"
down_revision: str | None = "20260526_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grading_risk_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("overall_risk_level", sa.String(length=16), nullable=False),
        sa.Column("overall_confidence_level", sa.String(length=16), nullable=False),
        sa.Column("liquidity_risk_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("spread_volatility_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("roi_volatility_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("grader_variability_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("reconciliation_variance_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("market_stability_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("evidence_strength_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("risk_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("confidence_weight", sa.Numeric(18, 8), nullable=True),
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
        sa.ForeignKeyConstraint(["recommendation_id"], ["grading_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_risk_snapshot_owner_replay"),
    )
    op.create_index(
        "ix_grading_risk_snapshot_owner_levels",
        "grading_risk_snapshot",
        ["owner_user_id", "overall_risk_level", "overall_confidence_level", "id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_risk_snapshot_scope_date",
        "grading_risk_snapshot",
        ["owner_user_id", "grading_candidate_id", "inventory_item_id", "canonical_comic_issue_id", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "grading_risk_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_risk_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_risk_snapshot_id"], ["grading_risk_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_risk_evidence_snapshot_created",
        "grading_risk_evidence",
        ["grading_risk_snapshot_id", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "confidence_factor_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("grading_risk_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("factor_key", sa.String(length=40), nullable=False),
        sa.Column("factor_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("weighting", sa.Numeric(10, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_risk_snapshot_id"], ["grading_risk_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_confidence_factor_snapshot_risk_factor",
        "confidence_factor_snapshot",
        ["grading_risk_snapshot_id", "factor_key", "id"],
        unique=False,
    )

    op.create_table(
        "risk_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("grading_candidate_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("overall_risk_level", sa.String(length=16), nullable=False),
        sa.Column("overall_confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_adjusted_roi", sa.Numeric(18, 8), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["grading_candidate_id"], ["grading_candidate.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "overall_risk_level",
            "overall_confidence_level",
            "snapshot_date",
            "checksum",
            name="uq_risk_history_signature",
        ),
    )
    op.create_index(
        "ix_risk_history_scope_date",
        "risk_history",
        ["owner_user_id", "grading_candidate_id", "inventory_item_id", "snapshot_date", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risk_history_scope_date", table_name="risk_history")
    op.drop_table("risk_history")
    op.drop_index("ix_confidence_factor_snapshot_risk_factor", table_name="confidence_factor_snapshot")
    op.drop_table("confidence_factor_snapshot")
    op.drop_index("ix_grading_risk_evidence_snapshot_created", table_name="grading_risk_evidence")
    op.drop_table("grading_risk_evidence")
    op.drop_index("ix_grading_risk_snapshot_scope_date", table_name="grading_risk_snapshot")
    op.drop_index("ix_grading_risk_snapshot_owner_levels", table_name="grading_risk_snapshot")
    op.drop_table("grading_risk_snapshot")
