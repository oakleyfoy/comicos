from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260914_0190"
down_revision = "20260913_0189"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_rebalance_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("rebalance_type", sa.String(length=32), nullable=False),
        sa.Column("target_key", sa.String(length=256), nullable=False),
        sa.Column("target_label", sa.String(length=512), nullable=False),
        sa.Column("exposure_value", sa.Float(), nullable=False),
        sa.Column("exposure_percent", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(length=24), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_rebalance_owner_type_key",
        "portfolio_rebalance_recommendation",
        ["owner_user_id", "rebalance_type", "target_key", "created_at", "id"],
    )
    op.create_index(
        "ix_portfolio_rebalance_owner_action",
        "portfolio_rebalance_recommendation",
        ["owner_user_id", "recommended_action", "id"],
    )
    op.create_index(
        op.f("ix_portfolio_rebalance_recommendation_owner_user_id"),
        "portfolio_rebalance_recommendation",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_rebalance_recommendation_owner_user_id"), table_name="portfolio_rebalance_recommendation")
    op.drop_index("ix_portfolio_rebalance_owner_action", table_name="portfolio_rebalance_recommendation")
    op.drop_index("ix_portfolio_rebalance_owner_type_key", table_name="portfolio_rebalance_recommendation")
    op.drop_table("portfolio_rebalance_recommendation")
