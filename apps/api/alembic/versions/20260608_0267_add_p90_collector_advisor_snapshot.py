"""add p90 collector advisor snapshot

Revision ID: 20260608_0267
Revises: 20260608_0266
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0267"
down_revision = "20260608_0266"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p90_collector_advisor_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("buy_actions", sa.JSON(), nullable=False),
        sa.Column("sell_actions", sa.JSON(), nullable=False),
        sa.Column("grade_actions", sa.JSON(), nullable=False),
        sa.Column("watch_actions", sa.JSON(), nullable=False),
        sa.Column("todays_actions", sa.JSON(), nullable=False),
        sa.Column("recent_activity", sa.JSON(), nullable=False),
        sa.Column("market_alerts", sa.JSON(), nullable=False),
        sa.Column("total_actions", sa.Integer(), nullable=False),
        sa.Column("estimated_profit", sa.Float(), nullable=False),
        sa.Column("estimated_savings", sa.Float(), nullable=False),
        sa.Column("portfolio_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p90_advisor_owner_date", "p90_collector_advisor_snapshot", ["owner_user_id", "snapshot_date"])
    op.create_index(
        op.f("ix_p90_collector_advisor_snapshot_owner_user_id"),
        "p90_collector_advisor_snapshot",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_p90_collector_advisor_snapshot_owner_user_id"), table_name="p90_collector_advisor_snapshot")
    op.drop_index("ix_p90_advisor_owner_date", table_name="p90_collector_advisor_snapshot")
    op.drop_table("p90_collector_advisor_snapshot")
