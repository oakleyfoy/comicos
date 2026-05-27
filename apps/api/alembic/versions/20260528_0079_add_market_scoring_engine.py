"""P39-03 market scoring engine."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0079"
down_revision: str | None = "20260528_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_acquisition_score_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("total_candidates_scored", sa.Integer(), nullable=False),
        sa.Column("avg_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("avg_liquidity_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("avg_grading_upside_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("high_value_count", sa.Integer(), nullable=False),
        sa.Column("strong_buy_count", sa.Integer(), nullable=False),
        sa.Column("buy_count", sa.Integer(), nullable=False),
        sa.Column("watch_count", sa.Integer(), nullable=False),
        sa.Column("ignore_count", sa.Integer(), nullable=False),
        sa.Column("portfolio_alignment_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_alignment_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("diversification_alignment_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_score_snapshot_owner_signature",
        ),
    )
    op.create_index(
        "ix_market_acquisition_score_snapshot_owner_date",
        "market_acquisition_score_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )

    op.create_table(
        "market_acquisition_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_score_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("normalized_candidate_id", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("acquisition_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("portfolio_fit_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("grading_upside_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("concentration_reduction_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("diversification_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("risk_penalty_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("final_rank_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_label", sa.String(length=24), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["market_acquisition_score_snapshot_id"], ["market_acquisition_score_snapshot.id"]),
        sa.ForeignKeyConstraint(["normalized_candidate_id"], ["market_acquisition_normalized_candidate.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_acquisition_score_snapshot_id",
            "normalized_candidate_id",
            name="uq_market_acquisition_score_snapshot_candidate",
        ),
    )
    op.create_index(
        "ix_market_acquisition_score_owner_label",
        "market_acquisition_score",
        ["owner_user_id", "recommendation_label", "final_rank_score", "id"],
    )

    op.create_table(
        "market_acquisition_score_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["score_id"], ["market_acquisition_score.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_score_evidence_score_type",
        "market_acquisition_score_evidence",
        ["score_id", "evidence_type", "id"],
    )

    op.create_table(
        "market_acquisition_score_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("normalized_candidate_id", sa.Integer(), nullable=False),
        sa.Column("acquisition_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("recommendation_label", sa.String(length=24), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["normalized_candidate_id"], ["market_acquisition_normalized_candidate.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "normalized_candidate_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_score_history_signature",
        ),
    )
    op.create_index(
        "ix_market_acquisition_score_history_owner_date",
        "market_acquisition_score_history",
        ["owner_user_id", "snapshot_date", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_acquisition_score_history_owner_date", table_name="market_acquisition_score_history")
    op.drop_table("market_acquisition_score_history")
    op.drop_index(
        "ix_market_acquisition_score_evidence_score_type",
        table_name="market_acquisition_score_evidence",
    )
    op.drop_table("market_acquisition_score_evidence")
    op.drop_index("ix_market_acquisition_score_owner_label", table_name="market_acquisition_score")
    op.drop_table("market_acquisition_score")
    op.drop_index(
        "ix_market_acquisition_score_snapshot_owner_date",
        table_name="market_acquisition_score_snapshot",
    )
    op.drop_table("market_acquisition_score_snapshot")
