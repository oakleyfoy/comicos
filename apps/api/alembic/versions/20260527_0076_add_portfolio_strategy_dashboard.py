"""P38-07 deterministic portfolio strategy dashboard."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0076"
down_revision: str | None = "20260527_0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_strategy_dashboard_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("portfolio_count", sa.Integer(), nullable=False),
        sa.Column("total_portfolio_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_cost_basis", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_realized_sales", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("diversification_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_efficiency_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("concentration_risk_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("dead_capital_estimate", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("duplicate_cluster_count", sa.Integer(), nullable=False),
        sa.Column("overexposed_category_count", sa.Integer(), nullable=False),
        sa.Column("hold_recommendation_count", sa.Integer(), nullable=False),
        sa.Column("sell_recommendation_count", sa.Integer(), nullable=False),
        sa.Column("reduce_exposure_count", sa.Integer(), nullable=False),
        sa.Column("acquisition_opportunity_count", sa.Integer(), nullable=False),
        sa.Column("elite_acquisition_count", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_count", sa.Integer(), nullable=False),
        sa.Column("liquid_inventory_percentage", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("illiquid_inventory_percentage", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "replay_key",
            name="uq_portfolio_strategy_dashboard_snapshot_owner_replay",
        ),
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_snapshot_owner_date",
        "portfolio_strategy_dashboard_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_snapshot_checksum",
        "portfolio_strategy_dashboard_snapshot",
        ["checksum"],
    )

    op.create_table(
        "portfolio_strategy_dashboard_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_decimal", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("metric_value_text", sa.Text(), nullable=True),
        sa.Column("metric_metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["portfolio_strategy_dashboard_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dashboard_snapshot_id",
            "metric_key",
            name="uq_portfolio_strategy_dashboard_metric_snapshot_key",
        ),
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_metric_snapshot",
        "portfolio_strategy_dashboard_metric",
        ["dashboard_snapshot_id"],
    )

    op.create_table(
        "portfolio_strategy_dashboard_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("alert_replay_key", sa.String(length=200), nullable=False),
        sa.Column("source_portfolio_id", sa.Integer(), nullable=True),
        sa.Column("source_inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["source_portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "alert_replay_key",
            name="uq_portfolio_strategy_dashboard_alert_owner_replay",
        ),
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_alert_owner_created",
        "portfolio_strategy_dashboard_alert",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_alert_type_severity",
        "portfolio_strategy_dashboard_alert",
        ["alert_type", "severity"],
    )

    op.create_table(
        "portfolio_strategy_dashboard_feed_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("deterministic_key", sa.String(length=200), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["portfolio_strategy_dashboard_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "deterministic_key",
            name="uq_portfolio_strategy_dashboard_feed_owner_key",
        ),
    )
    op.create_index(
        "ix_portfolio_strategy_dashboard_feed_owner_created",
        "portfolio_strategy_dashboard_feed_event",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_strategy_dashboard_feed_owner_created", table_name="portfolio_strategy_dashboard_feed_event")
    op.drop_table("portfolio_strategy_dashboard_feed_event")
    op.drop_index("ix_portfolio_strategy_dashboard_alert_type_severity", table_name="portfolio_strategy_dashboard_alert")
    op.drop_index("ix_portfolio_strategy_dashboard_alert_owner_created", table_name="portfolio_strategy_dashboard_alert")
    op.drop_table("portfolio_strategy_dashboard_alert")
    op.drop_index("ix_portfolio_strategy_dashboard_metric_snapshot", table_name="portfolio_strategy_dashboard_metric")
    op.drop_table("portfolio_strategy_dashboard_metric")
    op.drop_index(
        "ix_portfolio_strategy_dashboard_snapshot_checksum",
        table_name="portfolio_strategy_dashboard_snapshot",
    )
    op.drop_index(
        "ix_portfolio_strategy_dashboard_snapshot_owner_date",
        table_name="portfolio_strategy_dashboard_snapshot",
    )
    op.drop_table("portfolio_strategy_dashboard_snapshot")
