"""P36-06 listing intelligence foundation.

Revision ID: 20260525_0058
Revises: 20260525_0057
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0058"
down_revision: str | None = "20260525_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing_intelligence_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=True),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("intelligence_status", sa.String(length=24), nullable=False),
        sa.Column("completeness_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("image_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("title_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("description_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("pricing_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("export_readiness_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("sale_outcome_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("stale_risk_flag", sa.Boolean(), nullable=False),
        sa.Column("missing_required_fields_json", sa.JSON(), nullable=False),
        sa.Column("warning_flags_json", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.UniqueConstraint("owner_user_id", "listing_id", "snapshot_date", name="uq_listing_intelligence_snapshot_listing_date"),
    )
    op.create_index("ix_listing_intelligence_snapshot_owner_date", "listing_intelligence_snapshot", ["owner_user_id", "snapshot_date", "id"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_owner_status", "listing_intelligence_snapshot", ["owner_user_id", "intelligence_status"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_listing", "listing_intelligence_snapshot", ["listing_id"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_inventory", "listing_intelligence_snapshot", ["inventory_item_id"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_channel", "listing_intelligence_snapshot", ["channel"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_checksum", "listing_intelligence_snapshot", ["checksum"], unique=False)
    op.create_index("ix_listing_intelligence_snapshot_stale_risk_flag", "listing_intelligence_snapshot", ["stale_risk_flag"], unique=False)

    op.create_table(
        "listing_intelligence_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("intelligence_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=24), nullable=False),
        sa.Column("source_listing_id", sa.Integer(), nullable=True),
        sa.Column("source_export_run_id", sa.Integer(), nullable=True),
        sa.Column("source_sale_id", sa.Integer(), nullable=True),
        sa.Column("source_liquidity_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("source_convention_event_id", sa.Integer(), nullable=True),
        sa.Column("evidence_key", sa.String(length=128), nullable=False),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["intelligence_snapshot_id"], ["listing_intelligence_snapshot.id"]),
        sa.ForeignKeyConstraint(["source_listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["source_export_run_id"], ["listing_export_run.id"]),
        sa.ForeignKeyConstraint(["source_sale_id"], ["sale_record.id"]),
        sa.ForeignKeyConstraint(["source_liquidity_snapshot_id"], ["inventory_liquidity_snapshot.id"]),
        sa.ForeignKeyConstraint(["source_convention_event_id"], ["convention_event.id"]),
    )
    op.create_index(
        "ix_listing_intelligence_evidence_snapshot_key",
        "listing_intelligence_evidence",
        ["intelligence_snapshot_id", "evidence_type", "evidence_key", "id"],
        unique=False,
    )
    op.create_index("ix_listing_intelligence_evidence_listing", "listing_intelligence_evidence", ["source_listing_id"], unique=False)
    op.create_index("ix_listing_intelligence_evidence_export_run", "listing_intelligence_evidence", ["source_export_run_id"], unique=False)
    op.create_index("ix_listing_intelligence_evidence_sale", "listing_intelligence_evidence", ["source_sale_id"], unique=False)
    op.create_index("ix_listing_intelligence_evidence_liquidity", "listing_intelligence_evidence", ["source_liquidity_snapshot_id"], unique=False)
    op.create_index("ix_listing_intelligence_evidence_convention", "listing_intelligence_evidence", ["source_convention_event_id"], unique=False)

    op.create_table(
        "listing_completeness_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("intelligence_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("check_key", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["intelligence_snapshot_id"], ["listing_intelligence_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.UniqueConstraint("intelligence_snapshot_id", "check_key", name="uq_listing_completeness_check_snapshot_key"),
    )
    op.create_index("ix_listing_completeness_check_snapshot", "listing_completeness_check", ["intelligence_snapshot_id", "id"], unique=False)
    op.create_index("ix_listing_completeness_check_owner_listing", "listing_completeness_check", ["owner_user_id", "listing_id"], unique=False)
    op.create_index("ix_listing_completeness_check_status", "listing_completeness_check", ["owner_user_id", "status"], unique=False)
    op.create_index("ix_listing_completeness_check_snapshot_date", "listing_completeness_check", ["snapshot_date"], unique=False)
    op.create_index("ix_listing_completeness_check_severity", "listing_completeness_check", ["severity"], unique=False)

    op.create_table(
        "listing_channel_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("total_listings", sa.Integer(), nullable=False),
        sa.Column("active_listings", sa.Integer(), nullable=False),
        sa.Column("sold_listings", sa.Integer(), nullable=False),
        sa.Column("cancelled_listings", sa.Integer(), nullable=False),
        sa.Column("exported_count", sa.Integer(), nullable=False),
        sa.Column("sales_count", sa.Integer(), nullable=False),
        sa.Column("gross_sales_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_proceeds_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("median_days_to_sale", sa.Numeric(10, 2), nullable=True),
        sa.Column("stale_listing_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "channel", "snapshot_date", name="uq_listing_channel_perf_signature"),
    )
    op.create_index("ix_listing_channel_perf_owner_date", "listing_channel_performance_snapshot", ["owner_user_id", "snapshot_date", "id"], unique=False)
    op.create_index("ix_listing_channel_perf_owner_channel", "listing_channel_performance_snapshot", ["owner_user_id", "channel"], unique=False)
    op.create_index("ix_listing_channel_perf_checksum", "listing_channel_performance_snapshot", ["checksum"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_channel_perf_checksum", table_name="listing_channel_performance_snapshot")
    op.drop_index("ix_listing_channel_perf_owner_channel", table_name="listing_channel_performance_snapshot")
    op.drop_index("ix_listing_channel_perf_owner_date", table_name="listing_channel_performance_snapshot")
    op.drop_table("listing_channel_performance_snapshot")

    op.drop_index("ix_listing_completeness_check_severity", table_name="listing_completeness_check")
    op.drop_index("ix_listing_completeness_check_snapshot_date", table_name="listing_completeness_check")
    op.drop_index("ix_listing_completeness_check_status", table_name="listing_completeness_check")
    op.drop_index("ix_listing_completeness_check_owner_listing", table_name="listing_completeness_check")
    op.drop_index("ix_listing_completeness_check_snapshot", table_name="listing_completeness_check")
    op.drop_table("listing_completeness_check")

    op.drop_index("ix_listing_intelligence_evidence_convention", table_name="listing_intelligence_evidence")
    op.drop_index("ix_listing_intelligence_evidence_liquidity", table_name="listing_intelligence_evidence")
    op.drop_index("ix_listing_intelligence_evidence_sale", table_name="listing_intelligence_evidence")
    op.drop_index("ix_listing_intelligence_evidence_export_run", table_name="listing_intelligence_evidence")
    op.drop_index("ix_listing_intelligence_evidence_listing", table_name="listing_intelligence_evidence")
    op.drop_index("ix_listing_intelligence_evidence_snapshot_key", table_name="listing_intelligence_evidence")
    op.drop_table("listing_intelligence_evidence")

    op.drop_index("ix_listing_intelligence_snapshot_stale_risk_flag", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_checksum", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_channel", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_inventory", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_listing", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_owner_status", table_name="listing_intelligence_snapshot")
    op.drop_index("ix_listing_intelligence_snapshot_owner_date", table_name="listing_intelligence_snapshot")
    op.drop_table("listing_intelligence_snapshot")
