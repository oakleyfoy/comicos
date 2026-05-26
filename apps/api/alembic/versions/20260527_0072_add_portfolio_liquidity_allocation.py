"""P38-03 deterministic portfolio liquidity allocation intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0072"
down_revision: str | None = "20260527_0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_liquidity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("generation_scope_key", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("total_portfolio_fmv", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("liquid_portfolio_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("illiquid_portfolio_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("liquidity_weighted_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("liquidity_efficiency_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("liquidity_drag_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("concentration_risk_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("dead_capital_estimate", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("liquidity_balance_status", sa.String(length=24), nullable=False),
        sa.Column("high_liquidity_count", sa.Integer(), nullable=False),
        sa.Column("medium_liquidity_count", sa.Integer(), nullable=False),
        sa.Column("low_liquidity_count", sa.Integer(), nullable=False),
        sa.Column("illiquid_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            name="uq_portfolio_liquidity_snapshot_replay_signature",
        ),
    )
    op.create_index("ix_portfolio_liquidity_snapshot_owner_date", "portfolio_liquidity_snapshot", ["owner_user_id", "snapshot_date"])
    op.create_index(
        "ix_portfolio_liquidity_snapshot_owner_status",
        "portfolio_liquidity_snapshot",
        ["owner_user_id", "liquidity_balance_status"],
    )
    op.create_index(
        "ix_portfolio_liquidity_snapshot_owner_scope",
        "portfolio_liquidity_snapshot",
        ["owner_user_id", "generation_scope_key"],
    )
    op.create_index("ix_portfolio_liquidity_snapshot_checksum", "portfolio_liquidity_snapshot", ["checksum"])

    op.create_table(
        "portfolio_liquidity_bucket",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_liquidity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("liquidity_bucket", sa.String(length=16), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("weighted_liquidity_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("percentage_of_portfolio", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_liquidity_snapshot_id"], ["portfolio_liquidity_snapshot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_liquidity_snapshot_id",
            "liquidity_bucket",
            name="uq_portfolio_liquidity_bucket_signature",
        ),
    )
    op.create_index(
        "ix_portfolio_liquidity_bucket_portfolio_liquidity_snapshot_id",
        "portfolio_liquidity_bucket",
        ["portfolio_liquidity_snapshot_id"],
    )

    op.create_table(
        "portfolio_liquidity_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_liquidity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=64), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_liquidity_snapshot_id"], ["portfolio_liquidity_snapshot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_liquidity_evidence_snapshot_type",
        "portfolio_liquidity_evidence",
        ["portfolio_liquidity_snapshot_id", "evidence_type"],
    )

    op.create_table(
        "portfolio_liquidity_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("generation_scope_key", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False),
        sa.Column("liquidity_efficiency_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("liquidity_drag_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("concentration_risk_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("dead_capital_estimate", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("liquidity_balance_status", sa.String(length=24), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            "checksum",
            name="uq_portfolio_liquidity_history_replay_checksum",
        ),
    )
    op.create_index(
        "ix_portfolio_liquidity_history_owner_date",
        "portfolio_liquidity_history",
        ["owner_user_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_liquidity_history")
    op.drop_table("portfolio_liquidity_evidence")
    op.drop_table("portfolio_liquidity_bucket")
    op.drop_table("portfolio_liquidity_snapshot")
