"""P39-06 deterministic portfolio-market coupling ledger."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0082"
down_revision: str | None = "20260528_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_market_coupling_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_opportunity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_total_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("portfolio_total_items", sa.Integer(), nullable=False),
        sa.Column("portfolio_diversification_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("portfolio_concentration_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("portfolio_liquidity_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("market_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("aligned_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("misaligned_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("high_fit_market_items", sa.Integer(), nullable=False),
        sa.Column("low_fit_market_items", sa.Integer(), nullable=False),
        sa.Column("portfolio_market_alignment_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("diversification_gap_alignment_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("liquidity_gap_alignment_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("concentration_offset_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("signal_coverage_ratio", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("scoring_coverage_ratio", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("normalization_coverage_ratio", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_acquisition_opportunity_snapshot_id"],
            ["market_acquisition_opportunity_snapshot.id"],
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "market_acquisition_opportunity_snapshot_id",
            "snapshot_checksum",
            name="uq_portfolio_market_coupling_snapshot_signature",
        ),
    )
    op.create_index(
        "ix_pm_coupling_snap_owner_date",
        "portfolio_market_coupling_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_portfolio_market_coupling_snapshot_snapshot_checksum",
        "portfolio_market_coupling_snapshot",
        ["snapshot_checksum"],
    )

    op.create_table(
        "portfolio_market_coupling_edge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_market_coupling_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("market_normalized_candidate_id", sa.Integer(), nullable=False),
        sa.Column("market_acquisition_opportunity_item_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_item_id", sa.Integer(), nullable=True),
        sa.Column("coupling_type", sa.String(length=28), nullable=False),
        sa.Column("coupling_strength", sa.String(length=16), nullable=False),
        sa.Column("coupling_score", sa.Integer(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_acquisition_opportunity_item_id"],
            ["market_acquisition_opportunity_item.id"],
        ),
        sa.ForeignKeyConstraint(
            ["market_normalized_candidate_id"],
            ["market_acquisition_normalized_candidate.id"],
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_item_id"],
            ["portfolio_item.id"],
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_market_coupling_snapshot_id"],
            ["portfolio_market_coupling_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_market_coupling_snapshot_id",
            "market_normalized_candidate_id",
            "portfolio_item_id",
            "coupling_type",
            "market_acquisition_opportunity_item_id",
            name="uq_pm_coupling_edge_logical",
        ),
    )
    op.create_index(
        "ix_pm_coupling_edge_snap",
        "portfolio_market_coupling_edge",
        ["portfolio_market_coupling_snapshot_id", "id"],
    )
    op.create_index(
        "ix_pm_coupling_edge_candidate",
        "portfolio_market_coupling_edge",
        ["market_normalized_candidate_id", "id"],
    )
    op.create_index(
        "ix_pm_coupling_edge_portfolio_item",
        "portfolio_market_coupling_edge",
        ["portfolio_item_id", "id"],
    )
    op.create_index(
        "ix_pm_coupling_edge_type_str",
        "portfolio_market_coupling_edge",
        ["coupling_type", "coupling_strength", "id"],
    )

    op.create_table(
        "portfolio_market_coupling_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_market_coupling_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=28), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_market_coupling_snapshot_id"],
            ["portfolio_market_coupling_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pm_coupling_evidence_snap_type",
        "portfolio_market_coupling_evidence",
        ["portfolio_market_coupling_snapshot_id", "evidence_type", "id"],
    )

    op.create_table(
        "portfolio_market_coupling_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_market_coupling_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("alignment_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("market_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("high_fit_market_items", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(
            ["portfolio_market_coupling_snapshot_id"],
            ["portfolio_market_coupling_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_market_coupling_snapshot_id",
            name="uq_pm_coupling_history_snapshot_unique",
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_pm_coupling_history_snapshot_unique",
        "portfolio_market_coupling_history",
        type_="unique",
    )
    op.drop_table("portfolio_market_coupling_history")
    op.drop_index(
        "ix_pm_coupling_evidence_snap_type",
        table_name="portfolio_market_coupling_evidence",
    )
    op.drop_table("portfolio_market_coupling_evidence")
    op.drop_index("ix_pm_coupling_edge_type_str", table_name="portfolio_market_coupling_edge")
    op.drop_index("ix_pm_coupling_edge_portfolio_item", table_name="portfolio_market_coupling_edge")
    op.drop_index("ix_pm_coupling_edge_candidate", table_name="portfolio_market_coupling_edge")
    op.drop_index("ix_pm_coupling_edge_snap", table_name="portfolio_market_coupling_edge")
    op.drop_table("portfolio_market_coupling_edge")
    op.drop_index(
        "ix_portfolio_market_coupling_snapshot_snapshot_checksum",
        table_name="portfolio_market_coupling_snapshot",
    )
    op.drop_index("ix_pm_coupling_snap_owner_date", table_name="portfolio_market_coupling_snapshot")
    op.drop_table("portfolio_market_coupling_snapshot")
