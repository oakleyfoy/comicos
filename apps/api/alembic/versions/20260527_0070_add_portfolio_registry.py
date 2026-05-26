"""P38-01 portfolio registry, exposure, and allocation primitives."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0070"
down_revision: str | None = "20260526_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("portfolio_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_portfolio_owner_user_replay_key"),
    )
    op.create_index("ix_portfolio_owner_status", "portfolio", ["owner_user_id", "status", "id"], unique=False)
    op.create_index("ix_portfolio_owner_type", "portfolio", ["owner_user_id", "portfolio_type", "id"], unique=False)
    op.create_index("ix_portfolio_owner_user_id", "portfolio", ["owner_user_id"], unique=False)

    op.create_table(
        "portfolio_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("allocation_role", sa.String(length=32), nullable=False),
        sa.Column("allocated_value_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("allocated_value_source", sa.String(length=24), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_item_portfolio_active",
        "portfolio_item",
        ["portfolio_id", "inventory_item_id", "removed_at"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_item_inventory",
        "portfolio_item",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_item_portfolio_id",
        "portfolio_item",
        ["portfolio_id"],
        unique=False,
    )

    op.create_table(
        "portfolio_exposure_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("generation_scope_key", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("generation_batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("exposure_type", sa.String(length=32), nullable=False),
        sa.Column("exposure_key", sa.String(length=256), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_cost_basis_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_realized_sales_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("percentage_of_portfolio_value", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("percentage_of_portfolio_count", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("exposure_status", sa.String(length=24), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            "exposure_type",
            "exposure_key",
            name="uq_portfolio_exposure_scope_date_replay_dimension",
        ),
    )
    op.create_index(
        "ix_portfolio_exposure_owner_date",
        "portfolio_exposure_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_exposure_portfolio_date",
        "portfolio_exposure_snapshot",
        ["portfolio_id", "snapshot_date", "id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_exposure_batch",
        "portfolio_exposure_snapshot",
        ["generation_batch_checksum", "id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_exposure_type_key",
        "portfolio_exposure_snapshot",
        ["exposure_type", "exposure_key"],
        unique=False,
    )

    op.create_table(
        "portfolio_exposure_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_exposure_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_table", sa.String(length=80), nullable=True),
        sa.Column("evidence_value_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_exposure_snapshot_id"],
            ["portfolio_exposure_snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_exposure_evidence_snapshot",
        "portfolio_exposure_evidence",
        ["portfolio_exposure_snapshot_id", "id"],
        unique=False,
    )

    op.create_table(
        "portfolio_allocation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=True),
        sa.Column("generation_scope_key", sa.String(length=64), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("total_fmv_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_cost_basis_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_realized_sales_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("graded_item_count", sa.Integer(), nullable=False),
        sa.Column("raw_item_count", sa.Integer(), nullable=False),
        sa.Column("listed_item_count", sa.Integer(), nullable=False),
        sa.Column("sold_item_count", sa.Integer(), nullable=False),
        sa.Column("high_liquidity_count", sa.Integer(), nullable=False),
        sa.Column("low_liquidity_count", sa.Integer(), nullable=False),
        sa.Column("grading_candidate_count", sa.Integer(), nullable=False),
        sa.Column("sale_candidate_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("convention_assigned_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            name="uq_portfolio_allocation_scope_date_replay",
        ),
    )
    op.create_index(
        "ix_portfolio_allocation_owner_date",
        "portfolio_allocation_snapshot",
        ["owner_user_id", "snapshot_date", "id"],
        unique=False,
    )

    op.create_table(
        "portfolio_lifecycle_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_lc_portfolio_created",
        "portfolio_lifecycle_event",
        ["portfolio_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_lc_portfolio_created", table_name="portfolio_lifecycle_event")
    op.drop_table("portfolio_lifecycle_event")

    op.drop_index("ix_portfolio_allocation_owner_date", table_name="portfolio_allocation_snapshot")
    op.drop_table("portfolio_allocation_snapshot")

    op.drop_index("ix_portfolio_exposure_evidence_snapshot", table_name="portfolio_exposure_evidence")
    op.drop_table("portfolio_exposure_evidence")

    op.drop_index("ix_portfolio_exposure_type_key", table_name="portfolio_exposure_snapshot")
    op.drop_index("ix_portfolio_exposure_batch", table_name="portfolio_exposure_snapshot")
    op.drop_index("ix_portfolio_exposure_portfolio_date", table_name="portfolio_exposure_snapshot")
    op.drop_index("ix_portfolio_exposure_owner_date", table_name="portfolio_exposure_snapshot")
    op.drop_table("portfolio_exposure_snapshot")

    op.drop_index("ix_portfolio_item_portfolio_id", table_name="portfolio_item")
    op.drop_index("ix_portfolio_item_inventory", table_name="portfolio_item")
    op.drop_index("ix_portfolio_item_portfolio_active", table_name="portfolio_item")
    op.drop_table("portfolio_item")

    op.drop_index("ix_portfolio_owner_user_id", table_name="portfolio")
    op.drop_index("ix_portfolio_owner_type", table_name="portfolio")
    op.drop_index("ix_portfolio_owner_status", table_name="portfolio")
    op.drop_table("portfolio")
