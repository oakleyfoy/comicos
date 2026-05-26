"""P36-04 liquidity engine foundation (deterministic inventory movement analytics).

Revision ID: 20260525_0056
Revises: 20260525_0055
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0056"
down_revision: str | None = "20260525_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_liquidity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=True),
        sa.Column("liquidity_status", sa.String(length=24), nullable=False),
        sa.Column("days_on_market_median", sa.Numeric(10, 2), nullable=True),
        sa.Column("days_to_sale_median", sa.Numeric(10, 2), nullable=True),
        sa.Column("sell_through_rate_pct", sa.Numeric(10, 2), nullable=False),
        sa.Column("stale_listing_rate_pct", sa.Numeric(10, 2), nullable=False),
        sa.Column("relist_rate_pct", sa.Numeric(10, 2), nullable=False),
        sa.Column("successful_sale_count", sa.Integer(), nullable=False),
        sa.Column("failed_listing_count", sa.Integer(), nullable=False),
        sa.Column("active_listing_count", sa.Integer(), nullable=False),
        sa.Column("liquidity_confidence", sa.String(length=24), nullable=False),
        sa.Column("evaluation_window_days", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint(
            "owner_user_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "channel",
            "evaluation_window_days",
            "snapshot_date",
            name="uq_inventory_liquidity_snapshot_signature",
        ),
    )
    op.create_index("ix_inventory_liquidity_snapshot_owner_date", "inventory_liquidity_snapshot", ["owner_user_id", "snapshot_date", "id"], unique=False)
    op.create_index("ix_inventory_liquidity_snapshot_owner_status", "inventory_liquidity_snapshot", ["owner_user_id", "liquidity_status"], unique=False)
    op.create_index(op.f("ix_inventory_liquidity_snapshot_item"), "inventory_liquidity_snapshot", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_inventory_liquidity_snapshot_canonical"), "inventory_liquidity_snapshot", ["canonical_comic_issue_id"], unique=False)
    op.create_index(op.f("ix_inventory_liquidity_snapshot_channel"), "inventory_liquidity_snapshot", ["channel"], unique=False)

    op.create_table(
        "inventory_liquidity_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("liquidity_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=24), nullable=False),
        sa.Column("source_listing_id", sa.Integer(), nullable=True),
        sa.Column("source_sale_id", sa.Integer(), nullable=True),
        sa.Column("source_export_run_id", sa.Integer(), nullable=True),
        sa.Column("days_on_market", sa.Numeric(10, 2), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["liquidity_snapshot_id"], ["inventory_liquidity_snapshot.id"]),
        sa.ForeignKeyConstraint(["source_export_run_id"], ["listing_export_run.id"]),
        sa.ForeignKeyConstraint(["source_listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["source_sale_id"], ["sale_record.id"]),
    )
    op.create_index(
        "ix_inventory_liquidity_evidence_snapshot_type",
        "inventory_liquidity_evidence",
        ["liquidity_snapshot_id", "evidence_type", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_liquidity_evidence_liquidity_snapshot_id"),
        "inventory_liquidity_evidence",
        ["liquidity_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_liquidity_evidence_listing"),
        "inventory_liquidity_evidence",
        ["source_listing_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inventory_liquidity_evidence_sale"),
        "inventory_liquidity_evidence",
        ["source_sale_id"],
        unique=False,
    )

    op.create_table(
        "listing_velocity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("first_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("days_active", sa.Numeric(10, 2), nullable=True),
        sa.Column("relist_count", sa.Integer(), nullable=False),
        sa.Column("price_change_count", sa.Integer(), nullable=False),
        sa.Column("final_status", sa.String(length=24), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("listing_id", "snapshot_date", name="uq_listing_velocity_snapshot_listing_date"),
    )
    op.create_index("ix_listing_velocity_snapshot_owner_date", "listing_velocity_snapshot", ["owner_user_id", "snapshot_date", "id"], unique=False)
    op.create_index(op.f("ix_listing_velocity_snapshot_listing"), "listing_velocity_snapshot", ["listing_id"], unique=False)
    op.create_index(op.f("ix_listing_velocity_snapshot_channel"), "listing_velocity_snapshot", ["owner_user_id", "final_status"], unique=False)

    op.create_table(
        "listing_staleness_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("threshold_days", sa.Integer(), nullable=False),
        sa.Column("days_active", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("listing_id", "event_type", "threshold_days", name="uq_listing_staleness_event_signature"),
    )
    op.create_index("ix_listing_staleness_event_owner_created", "listing_staleness_event", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index(op.f("ix_listing_staleness_event_listing"), "listing_staleness_event", ["listing_id"], unique=False)
    op.create_index(op.f("ix_listing_staleness_event_event_type"), "listing_staleness_event", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_listing_staleness_event_event_type"), table_name="listing_staleness_event")
    op.drop_index(op.f("ix_listing_staleness_event_listing"), table_name="listing_staleness_event")
    op.drop_index("ix_listing_staleness_event_owner_created", table_name="listing_staleness_event")
    op.drop_table("listing_staleness_event")

    op.drop_index(op.f("ix_listing_velocity_snapshot_channel"), table_name="listing_velocity_snapshot")
    op.drop_index(op.f("ix_listing_velocity_snapshot_listing"), table_name="listing_velocity_snapshot")
    op.drop_index("ix_listing_velocity_snapshot_owner_date", table_name="listing_velocity_snapshot")
    op.drop_table("listing_velocity_snapshot")

    op.drop_index(op.f("ix_inventory_liquidity_evidence_sale"), table_name="inventory_liquidity_evidence")
    op.drop_index(op.f("ix_inventory_liquidity_evidence_listing"), table_name="inventory_liquidity_evidence")
    op.drop_index(op.f("ix_inventory_liquidity_evidence_liquidity_snapshot_id"), table_name="inventory_liquidity_evidence")
    op.drop_index("ix_inventory_liquidity_evidence_snapshot_type", table_name="inventory_liquidity_evidence")
    op.drop_table("inventory_liquidity_evidence")

    op.drop_index(op.f("ix_inventory_liquidity_snapshot_channel"), table_name="inventory_liquidity_snapshot")
    op.drop_index(op.f("ix_inventory_liquidity_snapshot_canonical"), table_name="inventory_liquidity_snapshot")
    op.drop_index(op.f("ix_inventory_liquidity_snapshot_item"), table_name="inventory_liquidity_snapshot")
    op.drop_index("ix_inventory_liquidity_snapshot_owner_status", table_name="inventory_liquidity_snapshot")
    op.drop_index("ix_inventory_liquidity_snapshot_owner_date", table_name="inventory_liquidity_snapshot")
    op.drop_table("inventory_liquidity_snapshot")
