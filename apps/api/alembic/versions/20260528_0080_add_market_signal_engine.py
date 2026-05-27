"""P39-04 market signal engine."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0080"
down_revision: str | None = "20260528_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_acquisition_signal_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_score_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("total_signals", sa.Integer(), nullable=False),
        sa.Column("elite_signal_count", sa.Integer(), nullable=False),
        sa.Column("high_signal_count", sa.Integer(), nullable=False),
        sa.Column("medium_signal_count", sa.Integer(), nullable=False),
        sa.Column("low_signal_count", sa.Integer(), nullable=False),
        sa.Column("value_dislocation_count", sa.Integer(), nullable=False),
        sa.Column("liquidity_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("portfolio_gap_fill_count", sa.Integer(), nullable=False),
        sa.Column("concentration_reduction_count", sa.Integer(), nullable=False),
        sa.Column("grading_upside_count", sa.Integer(), nullable=False),
        sa.Column("redundant_asset_count", sa.Integer(), nullable=False),
        sa.Column("high_risk_asset_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_acquisition_score_snapshot_id"], ["market_acquisition_score_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "market_acquisition_score_snapshot_id",
            "checksum",
            name="uq_market_acquisition_signal_snapshot_signature",
        ),
    )
    op.create_index(
        "ix_market_acquisition_signal_snapshot_owner_date",
        "market_acquisition_signal_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )

    op.create_table(
        "market_acquisition_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_signal_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("scored_candidate_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.String(length=40), nullable=False),
        sa.Column("signal_strength", sa.String(length=16), nullable=False),
        sa.Column("signal_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("signal_reason_json", sa.JSON(), nullable=False),
        sa.Column("supporting_factors_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_acquisition_signal_snapshot_id"], ["market_acquisition_signal_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scored_candidate_id"], ["market_acquisition_score.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_acquisition_signal_snapshot_id",
            "scored_candidate_id",
            name="uq_market_acquisition_signal_snapshot_score",
        ),
    )
    op.create_index(
        "ix_market_acquisition_signal_owner_type_strength",
        "market_acquisition_signal",
        ["owner_user_id", "signal_type", "signal_strength", "id"],
    )

    op.create_table(
        "market_acquisition_signal_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_signal_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_acquisition_signal_id"], ["market_acquisition_signal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_signal_evidence_signal_type",
        "market_acquisition_signal_evidence",
        ["market_acquisition_signal_id", "evidence_type", "id"],
    )

    op.create_table(
        "market_acquisition_signal_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scored_candidate_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=40), nullable=False),
        sa.Column("signal_strength", sa.String(length=16), nullable=False),
        sa.Column("signal_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scored_candidate_id"], ["market_acquisition_score.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "scored_candidate_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_signal_history_signature",
        ),
    )
    op.create_index(
        "ix_market_acquisition_signal_history_owner_date",
        "market_acquisition_signal_history",
        ["owner_user_id", "snapshot_date", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_acquisition_signal_history_owner_date", table_name="market_acquisition_signal_history")
    op.drop_table("market_acquisition_signal_history")
    op.drop_index(
        "ix_market_acquisition_signal_evidence_signal_type",
        table_name="market_acquisition_signal_evidence",
    )
    op.drop_table("market_acquisition_signal_evidence")
    op.drop_index(
        "ix_market_acquisition_signal_owner_type_strength",
        table_name="market_acquisition_signal",
    )
    op.drop_table("market_acquisition_signal")
    op.drop_index(
        "ix_market_acquisition_signal_snapshot_owner_date",
        table_name="market_acquisition_signal_snapshot",
    )
    op.drop_table("market_acquisition_signal_snapshot")
