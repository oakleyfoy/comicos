"""P39-05 market opportunity snapshot engine."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0081"
down_revision: str | None = "20260528_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_acquisition_opportunity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_signal_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("opportunity_classification", sa.String(length=40), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
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
        sa.Column(
            "estimated_portfolio_gap_coverage",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("estimated_liquidity_gain", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "estimated_diversification_gain",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("estimated_risk_adjustment", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("avg_signal_strength", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("avg_acquisition_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("avg_confidence_level", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("avg_risk_level", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_acquisition_signal_snapshot_id"], ["market_acquisition_signal_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "market_acquisition_signal_snapshot_id",
            "snapshot_checksum",
            name="uq_market_acquisition_opportunity_snapshot_signature",
        ),
    )
    op.create_index(
        "ix_market_acquisition_opportunity_snapshot_owner_date",
        "market_acquisition_opportunity_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )

    op.create_table(
        "market_acquisition_opportunity_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_opportunity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_signal_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.String(length=40), nullable=False),
        sa.Column("signal_strength", sa.String(length=16), nullable=False),
        sa.Column("acquisition_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("contribution_weight", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["market_acquisition_normalized_candidate.id"]),
        sa.ForeignKeyConstraint(["market_acquisition_opportunity_snapshot_id"], ["market_acquisition_opportunity_snapshot.id"]),
        sa.ForeignKeyConstraint(["market_acquisition_signal_id"], ["market_acquisition_signal.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_acquisition_opportunity_snapshot_id",
            "market_acquisition_signal_id",
            name="uq_market_acquisition_opportunity_item_signal",
        ),
    )
    op.create_index(
        "ix_market_acquisition_opportunity_item_owner_filters",
        "market_acquisition_opportunity_item",
        ["owner_user_id", "signal_type", "signal_strength", "risk_level", "snapshot_date", "id"],
    )

    op.create_table(
        "market_acquisition_opportunity_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_opportunity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_acquisition_opportunity_snapshot_id"],
            ["market_acquisition_opportunity_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_opportunity_evidence_snap_type",
        "market_acquisition_opportunity_evidence",
        ["market_acquisition_opportunity_snapshot_id", "evidence_type", "id"],
    )

    op.create_table(
        "market_acquisition_opportunity_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("market_acquisition_opportunity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("elite_signal_count", sa.Integer(), nullable=False),
        sa.Column("high_signal_count", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_portfolio_gap_coverage",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "estimated_diversification_gain",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_acquisition_opportunity_snapshot_id"], ["market_acquisition_opportunity_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_opportunity_history_owner_date",
        "market_acquisition_opportunity_history",
        ["owner_user_id", "snapshot_date", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_acquisition_opportunity_history_owner_date",
        table_name="market_acquisition_opportunity_history",
    )
    op.drop_table("market_acquisition_opportunity_history")
    op.drop_index(
        "ix_market_acquisition_opportunity_evidence_snap_type",
        table_name="market_acquisition_opportunity_evidence",
    )
    op.drop_table("market_acquisition_opportunity_evidence")
    op.drop_index(
        "ix_market_acquisition_opportunity_item_owner_filters",
        table_name="market_acquisition_opportunity_item",
    )
    op.drop_table("market_acquisition_opportunity_item")
    op.drop_index(
        "ix_market_acquisition_opportunity_snapshot_owner_date",
        table_name="market_acquisition_opportunity_snapshot",
    )
    op.drop_table("market_acquisition_opportunity_snapshot")
