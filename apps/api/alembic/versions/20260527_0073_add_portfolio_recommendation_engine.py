"""P38-04 deterministic portfolio hold/sell recommendation intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0073"
down_revision: str | None = "20260527_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_action", sa.String(length=24), nullable=False),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("estimated_liquidity_impact", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("estimated_capital_release", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("estimated_portfolio_efficiency_gain", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("expected_roi_if_graded", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=False),
        sa.Column("warning_flags_json", sa.JSON(), nullable=False),
        sa.Column("recommendation_status", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "snapshot_date",
            "replay_key",
            "checksum",
            name="uq_portfolio_recommendation_signature",
        ),
    )
    op.create_index(
        "ix_portfolio_recommendation_owner_status",
        "portfolio_recommendation",
        ["owner_user_id", "recommendation_status", "recommendation_action", "id"],
    )
    op.create_index(
        "ix_portfolio_recommendation_owner_strength",
        "portfolio_recommendation",
        ["owner_user_id", "recommendation_strength", "confidence_level", "risk_level", "id"],
    )
    op.create_index(
        "ix_portfolio_recommendation_scope_date",
        "portfolio_recommendation",
        ["owner_user_id", "portfolio_id", "inventory_item_id", "snapshot_date", "id"],
    )
    op.create_index("ix_portfolio_recommendation_checksum", "portfolio_recommendation", ["checksum"])

    op.create_table(
        "portfolio_recommendation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_recommendation_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_recommendation_id"],
            ["portfolio_recommendation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_recommendation_evidence_recommendation_created",
        "portfolio_recommendation_evidence",
        ["portfolio_recommendation_id", "created_at", "id"],
    )

    op.create_table(
        "portfolio_recommendation_scenario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_recommendation_id", sa.Integer(), nullable=False),
        sa.Column("scenario_name", sa.String(length=16), nullable=False),
        sa.Column("projected_capital_release", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("projected_liquidity_gain", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("projected_portfolio_impact", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_recommendation_id"],
            ["portfolio_recommendation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_recommendation_scenario_recommendation_name",
        "portfolio_recommendation_scenario",
        ["portfolio_recommendation_id", "scenario_name", "id"],
    )

    op.create_table(
        "portfolio_recommendation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_action", sa.String(length=24), nullable=False),
        sa.Column("recommendation_strength", sa.String(length=16), nullable=False),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "recommendation_action",
            "recommendation_strength",
            "confidence_level",
            "risk_level",
            "snapshot_date",
            "checksum",
            name="uq_portfolio_recommendation_history_signature",
        ),
    )
    op.create_index(
        "ix_portfolio_recommendation_history_scope_date",
        "portfolio_recommendation_history",
        ["owner_user_id", "portfolio_id", "inventory_item_id", "snapshot_date", "id"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_recommendation_history")
    op.drop_table("portfolio_recommendation_scenario")
    op.drop_table("portfolio_recommendation_evidence")
    op.drop_index("ix_portfolio_recommendation_checksum", table_name="portfolio_recommendation")
    op.drop_index("ix_portfolio_recommendation_scope_date", table_name="portfolio_recommendation")
    op.drop_index("ix_portfolio_recommendation_owner_strength", table_name="portfolio_recommendation")
    op.drop_index("ix_portfolio_recommendation_owner_status", table_name="portfolio_recommendation")
    op.drop_table("portfolio_recommendation")
