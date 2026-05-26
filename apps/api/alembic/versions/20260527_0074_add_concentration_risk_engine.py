"""P38-05 deterministic concentration-risk intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0074"
down_revision: str | None = "20260527_0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "concentration_risk_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("concentration_type", sa.String(length=32), nullable=False),
        sa.Column("concentration_key", sa.String(length=256), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("percentage_of_portfolio", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("concentration_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_weighted_concentration", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("exposure_status", sa.String(length=24), nullable=False),
        sa.Column("diversification_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "snapshot_date",
            "replay_key",
            name="uq_concentration_risk_snapshot_replay",
        ),
    )
    op.create_index(
        "ix_concentration_risk_owner_date",
        "concentration_risk_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_concentration_risk_owner_status",
        "concentration_risk_snapshot",
        ["owner_user_id", "exposure_status", "concentration_type", "id"],
    )
    op.create_index(
        "ix_concentration_risk_scope_key",
        "concentration_risk_snapshot",
        ["owner_user_id", "portfolio_id", "concentration_type", "concentration_key", "id"],
    )

    op.create_table(
        "concentration_risk_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("concentration_risk_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["concentration_risk_snapshot_id"], ["concentration_risk_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_concentration_risk_evidence_snapshot_type",
        "concentration_risk_evidence",
        ["concentration_risk_snapshot_id", "evidence_type", "id"],
    )

    op.create_table(
        "concentration_risk_factor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("concentration_risk_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("factor_key", sa.String(length=40), nullable=False),
        sa.Column("factor_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("weighting", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["concentration_risk_snapshot_id"], ["concentration_risk_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "concentration_risk_snapshot_id",
            "factor_key",
            name="uq_concentration_risk_factor_snapshot_key",
        ),
    )

    op.create_table(
        "concentration_risk_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("concentration_type", sa.String(length=32), nullable=False),
        sa.Column("concentration_key", sa.String(length=256), nullable=False),
        sa.Column("exposure_status", sa.String(length=24), nullable=False),
        sa.Column("concentration_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("diversification_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "snapshot_date",
            "checksum",
            name="uq_concentration_risk_history_signature",
        ),
    )
    op.create_index(
        "ix_concentration_risk_history_owner_date",
        "concentration_risk_history",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_concentration_risk_history_scope_key",
        "concentration_risk_history",
        ["owner_user_id", "portfolio_id", "concentration_type", "concentration_key", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_concentration_risk_history_scope_key", table_name="concentration_risk_history")
    op.drop_index("ix_concentration_risk_history_owner_date", table_name="concentration_risk_history")
    op.drop_table("concentration_risk_history")
    op.drop_table("concentration_risk_factor")
    op.drop_index("ix_concentration_risk_evidence_snapshot_type", table_name="concentration_risk_evidence")
    op.drop_table("concentration_risk_evidence")
    op.drop_index("ix_concentration_risk_scope_key", table_name="concentration_risk_snapshot")
    op.drop_index("ix_concentration_risk_owner_status", table_name="concentration_risk_snapshot")
    op.drop_index("ix_concentration_risk_owner_date", table_name="concentration_risk_snapshot")
    op.drop_table("concentration_risk_snapshot")
