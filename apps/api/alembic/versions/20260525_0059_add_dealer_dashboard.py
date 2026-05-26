"""P36-07 dealer dashboard tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0059"
down_revision: str | None = "20260525_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dealer_dashboard_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("active_listing_count", sa.Integer(), nullable=False),
        sa.Column("export_ready_count", sa.Integer(), nullable=False),
        sa.Column("incomplete_listing_count", sa.Integer(), nullable=False),
        sa.Column("stale_listing_count", sa.Integer(), nullable=False),
        sa.Column("active_convention_count", sa.Integer(), nullable=False),
        sa.Column("assigned_convention_inventory_count", sa.Integer(), nullable=False),
        sa.Column("open_sale_session_count", sa.Integer(), nullable=False),
        sa.Column("gross_sales_30d", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_sales_30d", sa.Numeric(18, 2), nullable=False),
        sa.Column("realized_profit_30d", sa.Numeric(18, 2), nullable=False),
        sa.Column("liquidity_high_count", sa.Integer(), nullable=False),
        sa.Column("liquidity_low_count", sa.Integer(), nullable=False),
        sa.Column("export_run_count_30d", sa.Integer(), nullable=False),
        sa.Column("failed_export_count_30d", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_dealer_dashboard_snapshot_owner_replay"),
    )
    op.create_index(
        "ix_dealer_dashboard_snapshot_owner_date",
        "dealer_dashboard_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_dashboard_snapshot_checksum",
        "dealer_dashboard_snapshot",
        ["checksum"],
        unique=False,
    )

    op.create_table(
        "dealer_dashboard_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_decimal", sa.Numeric(18, 6), nullable=True),
        sa.Column("metric_value_text", sa.Text(), nullable=True),
        sa.Column("metric_metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_dashboard_snapshot.id"]),
        sa.UniqueConstraint("dashboard_snapshot_id", "metric_key", name="uq_dealer_dashboard_metric_snapshot_key"),
    )
    op.create_index(
        "ix_dealer_dashboard_metric_snapshot",
        "dealer_dashboard_metric",
        ["dashboard_snapshot_id"],
        unique=False,
    )

    op.create_table(
        "dealer_dashboard_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("alert_replay_key", sa.String(length=160), nullable=False),
        sa.Column("source_listing_id", sa.Integer(), nullable=True),
        sa.Column("source_inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("source_export_run_id", sa.Integer(), nullable=True),
        sa.Column("source_convention_event_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_dashboard_snapshot.id"]),
        sa.ForeignKeyConstraint(["source_listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["source_inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["source_export_run_id"], ["listing_export_run.id"]),
        sa.ForeignKeyConstraint(["source_convention_event_id"], ["convention_event.id"]),
        sa.UniqueConstraint("owner_user_id", "alert_replay_key", name="uq_dealer_dashboard_alert_owner_replay_key"),
    )
    op.create_index(
        "ix_dealer_dashboard_alert_owner_created",
        "dealer_dashboard_alert",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_dashboard_alert_owner_dashboard",
        "dealer_dashboard_alert",
        ["owner_user_id", "dashboard_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_dealer_dashboard_alert_type_severity",
        "dealer_dashboard_alert",
        ["alert_type", "severity"],
        unique=False,
    )

    op.create_table(
        "dealer_dashboard_feed_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("deterministic_key", sa.String(length=192), nullable=False),
        sa.Column("dashboard_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["dashboard_snapshot_id"], ["dealer_dashboard_snapshot.id"]),
        sa.UniqueConstraint("owner_user_id", "deterministic_key", name="uq_dealer_dashboard_feed_event_owner_key"),
    )
    op.create_index(
        "ix_dealer_dashboard_feed_owner_created",
        "dealer_dashboard_feed_event",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dealer_dashboard_feed_owner_created", table_name="dealer_dashboard_feed_event")
    op.drop_table("dealer_dashboard_feed_event")

    op.drop_index("ix_dealer_dashboard_alert_type_severity", table_name="dealer_dashboard_alert")
    op.drop_index("ix_dealer_dashboard_alert_owner_dashboard", table_name="dealer_dashboard_alert")
    op.drop_index("ix_dealer_dashboard_alert_owner_created", table_name="dealer_dashboard_alert")
    op.drop_table("dealer_dashboard_alert")

    op.drop_index("ix_dealer_dashboard_metric_snapshot", table_name="dealer_dashboard_metric")
    op.drop_table("dealer_dashboard_metric")

    op.drop_index("ix_dealer_dashboard_snapshot_checksum", table_name="dealer_dashboard_snapshot")
    op.drop_index("ix_dealer_dashboard_snapshot_owner_date", table_name="dealer_dashboard_snapshot")
    op.drop_table("dealer_dashboard_snapshot")
