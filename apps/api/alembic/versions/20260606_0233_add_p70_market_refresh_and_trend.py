"""P70-06 market refresh runs and FMV trend points."""

from alembic import op
import sqlalchemy as sa

revision = "20260606_0233"
down_revision = "20260606_0232"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p70_market_refresh_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_copy_count", sa.Integer(), nullable=False),
        sa.Column("books_refreshed", sa.Integer(), nullable=False),
        sa.Column("comps_fetched", sa.Integer(), nullable=False),
        sa.Column("fmv_snapshots_generated", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p70_market_refresh_run_owner_user_id", "p70_market_refresh_run", ["owner_user_id"])
    op.create_index("ix_p70_refresh_owner_started", "p70_market_refresh_run", ["owner_user_id", "started_at", "id"])

    op.create_table(
        "p70_market_fmv_trend_point",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("recorded_on", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blended_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("raw_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("sales_count", sa.Integer(), nullable=False),
        sa.Column("price_trend_7d", sa.String(length=16), nullable=False),
        sa.Column("price_trend_30d", sa.String(length=16), nullable=False),
        sa.Column("price_trend_90d", sa.String(length=16), nullable=False),
        sa.Column("provider_breakdown_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p68_market_price_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p70_market_fmv_trend_point_owner_user_id", "p70_market_fmv_trend_point", ["owner_user_id"])
    op.create_index("ix_p70_market_fmv_trend_point_inventory_copy_id", "p70_market_fmv_trend_point", ["inventory_copy_id"])
    op.create_index("ix_p70_trend_owner_copy_date", "p70_market_fmv_trend_point", ["owner_user_id", "inventory_copy_id", "recorded_on", "id"])


def downgrade() -> None:
    op.drop_index("ix_p70_trend_owner_copy_date", table_name="p70_market_fmv_trend_point")
    op.drop_index("ix_p70_market_fmv_trend_point_inventory_copy_id", table_name="p70_market_fmv_trend_point")
    op.drop_index("ix_p70_market_fmv_trend_point_owner_user_id", table_name="p70_market_fmv_trend_point")
    op.drop_table("p70_market_fmv_trend_point")
    op.drop_index("ix_p70_refresh_owner_started", table_name="p70_market_refresh_run")
    op.drop_index("ix_p70_market_refresh_run_owner_user_id", table_name="p70_market_refresh_run")
    op.drop_table("p70_market_refresh_run")
