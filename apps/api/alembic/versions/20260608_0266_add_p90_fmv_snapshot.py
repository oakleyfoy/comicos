"""Add P90 FMV Intelligence V2 snapshots."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0266"
down_revision = "20260608_0265"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p90_fmv_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("variant", sa.String(length=200), nullable=False),
        sa.Column("quick_sale_value", sa.Float(), nullable=False),
        sa.Column("market_value", sa.Float(), nullable=False),
        sa.Column("premium_value", sa.Float(), nullable=False),
        sa.Column("valuation_confidence", sa.String(length=8), nullable=False),
        sa.Column("trend_direction", sa.String(length=8), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False),
        sa.Column("sales_velocity", sa.String(length=16), nullable=False),
        sa.Column("listing_count", sa.Integer(), nullable=False),
        sa.Column("marketplace_count", sa.Integer(), nullable=False),
        sa.Column("valuation_source", sa.String(length=16), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "series",
            "issue_number",
            "variant",
            "snapshot_date",
            name="uq_p90_fmv_snap_day",
        ),
    )
    op.create_index(op.f("ix_p90_fmv_snapshot_owner_user_id"), "p90_fmv_snapshot", ["owner_user_id"])
    op.create_index(op.f("ix_p90_fmv_snapshot_series"), "p90_fmv_snapshot", ["series"])
    op.create_index(op.f("ix_p90_fmv_snapshot_valuation_confidence"), "p90_fmv_snapshot", ["valuation_confidence"])
    op.create_index(op.f("ix_p90_fmv_snapshot_valuation_source"), "p90_fmv_snapshot", ["valuation_source"])
    op.create_index("ix_p90_fmv_owner_date", "p90_fmv_snapshot", ["owner_user_id", "snapshot_date"])
    op.create_index("ix_p90_fmv_owner_conf", "p90_fmv_snapshot", ["owner_user_id", "valuation_confidence"])


def downgrade() -> None:
    op.drop_index("ix_p90_fmv_owner_conf", table_name="p90_fmv_snapshot")
    op.drop_index("ix_p90_fmv_owner_date", table_name="p90_fmv_snapshot")
    op.drop_index(op.f("ix_p90_fmv_snapshot_valuation_source"), table_name="p90_fmv_snapshot")
    op.drop_index(op.f("ix_p90_fmv_snapshot_valuation_confidence"), table_name="p90_fmv_snapshot")
    op.drop_index(op.f("ix_p90_fmv_snapshot_series"), table_name="p90_fmv_snapshot")
    op.drop_index(op.f("ix_p90_fmv_snapshot_owner_user_id"), table_name="p90_fmv_snapshot")
    op.drop_table("p90_fmv_snapshot")
