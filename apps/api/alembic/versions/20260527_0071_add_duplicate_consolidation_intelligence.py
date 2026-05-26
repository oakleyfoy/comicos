"""P38-02 duplicate clustering & deterministic consolidation intelligence."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0071"
down_revision: str | None = "20260527_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_cluster",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("cluster_key", sa.String(length=256), nullable=False),
        sa.Column("cluster_type", sa.String(length=32), nullable=False),
        sa.Column("generation_batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("graded_item_count", sa.Integer(), nullable=False),
        sa.Column("raw_item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_cost_basis_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("liquidity_profile", sa.String(length=16), nullable=False),
        sa.Column("duplication_status", sa.String(length=24), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "generation_batch_checksum",
            "cluster_type",
            "cluster_key",
            name="uq_duplicate_cluster_batch_type_key",
        ),
    )
    op.create_index("ix_duplicate_cluster_owner_date", "duplicate_cluster", ["owner_user_id", "snapshot_date", "id"])
    op.create_index(
        "ix_duplicate_cluster_owner_batch", "duplicate_cluster", ["owner_user_id", "generation_batch_checksum", "id"]
    )
    op.create_index(
        "ix_duplicate_cluster_owner_status", "duplicate_cluster", ["owner_user_id", "duplication_status", "id"]
    )
    op.create_index("ix_duplicate_cluster_owner_type", "duplicate_cluster", ["owner_user_id", "cluster_type", "id"])

    op.create_table(
        "duplicate_cluster_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("duplicate_cluster_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("grading_status", sa.String(length=24), nullable=False),
        sa.Column("estimated_strength_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("liquidity_score", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("current_fmv", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("recommendation_priority", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_cluster_id"], ["duplicate_cluster.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duplicate_cluster_id", "inventory_item_id", name="uq_dup_cluster_item_cluster_inv"),
    )
    op.create_index(
        "ix_duplicate_cluster_item_cluster", "duplicate_cluster_item", ["duplicate_cluster_id", "id"]
    )
    op.create_index(
        "ix_duplicate_cluster_item_inventory", "duplicate_cluster_item", ["inventory_item_id", "id"]
    )

    op.create_table(
        "duplicate_consolidation_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("duplicate_cluster_id", sa.Integer(), nullable=False),
        sa.Column("generation_batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("recommendation_action", sa.String(length=32), nullable=False),
        sa.Column("rationale_summary", sa.Text(), nullable=False),
        sa.Column("expected_capital_reduction", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("estimated_liquidity_improvement", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("estimated_portfolio_efficiency_gain", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("confidence_level", sa.String(length=16), nullable=False),
        sa.Column("recommendation_status", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_cluster_id"], ["duplicate_cluster.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duplicate_cluster_id", name="uq_dup_consolidation_one_per_cluster"),
    )
    op.create_index(
        "ix_dup_consolidation_owner_status",
        "duplicate_consolidation_recommendation",
        ["owner_user_id", "recommendation_status", "id"],
    )
    op.create_index(
        "ix_dup_consolidation_owner_action",
        "duplicate_consolidation_recommendation",
        ["owner_user_id", "recommendation_action", "id"],
    )
    op.create_index(
        "ix_dup_consolidation_owner_date",
        "duplicate_consolidation_recommendation",
        ["owner_user_id", "snapshot_date", "id"],
    )

    op.create_table(
        "duplicate_history_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("cluster_key", sa.String(length=256), nullable=False),
        sa.Column("cluster_type", sa.String(length=32), nullable=False),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("duplication_status", sa.String(length=24), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("generation_batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "cluster_key",
            "snapshot_date",
            "replay_key",
            "generation_batch_checksum",
            name="uq_duplicate_history_key_date_batch",
        ),
    )
    op.create_index(
        "ix_duplicate_history_owner_date", "duplicate_history_snapshot", ["owner_user_id", "snapshot_date", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_duplicate_history_owner_date", table_name="duplicate_history_snapshot")
    op.drop_table("duplicate_history_snapshot")

    op.drop_index("ix_dup_consolidation_owner_date", table_name="duplicate_consolidation_recommendation")
    op.drop_index("ix_dup_consolidation_owner_action", table_name="duplicate_consolidation_recommendation")
    op.drop_index("ix_dup_consolidation_owner_status", table_name="duplicate_consolidation_recommendation")
    op.drop_table("duplicate_consolidation_recommendation")

    op.drop_index("ix_duplicate_cluster_item_inventory", table_name="duplicate_cluster_item")
    op.drop_index("ix_duplicate_cluster_item_cluster", table_name="duplicate_cluster_item")
    op.drop_table("duplicate_cluster_item")

    op.drop_index("ix_duplicate_cluster_owner_type", table_name="duplicate_cluster")
    op.drop_index("ix_duplicate_cluster_owner_status", table_name="duplicate_cluster")
    op.drop_index("ix_duplicate_cluster_owner_batch", table_name="duplicate_cluster")
    op.drop_index("ix_duplicate_cluster_owner_date", table_name="duplicate_cluster")
    op.drop_table("duplicate_cluster")
