from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260903_0179"
down_revision = "20260902_0178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_budget",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("monthly_budget", sa.Float(), nullable=False),
        sa.Column("weekly_budget", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_purchase_budget_owner"),
    )
    op.create_index("ix_purchase_budget_owner_active", "purchase_budget", ["owner_user_id", "is_active", "id"])

    op.create_table(
        "purchase_budget_allocation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_tier", sa.String(length=24), nullable=False),
        sa.Column("allocated_amount", sa.Float(), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_budget_alloc_owner_release",
        "purchase_budget_allocation",
        ["owner_user_id", "release_id", "created_at", "id"],
    )
    op.create_index(
        "ix_purchase_budget_alloc_owner_tier",
        "purchase_budget_allocation",
        ["owner_user_id", "recommendation_tier", "id"],
    )
    op.create_index(
        "ix_purchase_budget_alloc_owner_rank",
        "purchase_budget_allocation",
        ["owner_user_id", "priority_rank", "id"],
    )
    op.create_index(
        op.f("ix_purchase_budget_allocation_owner_user_id"),
        "purchase_budget_allocation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_purchase_budget_allocation_release_id"),
        "purchase_budget_allocation",
        ["release_id"],
    )
    op.create_index(
        op.f("ix_purchase_budget_allocation_priority_rank"),
        "purchase_budget_allocation",
        ["priority_rank"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_budget_allocation_priority_rank"), table_name="purchase_budget_allocation")
    op.drop_index(op.f("ix_purchase_budget_allocation_release_id"), table_name="purchase_budget_allocation")
    op.drop_index(op.f("ix_purchase_budget_allocation_owner_user_id"), table_name="purchase_budget_allocation")
    op.drop_index("ix_purchase_budget_alloc_owner_rank", table_name="purchase_budget_allocation")
    op.drop_index("ix_purchase_budget_alloc_owner_tier", table_name="purchase_budget_allocation")
    op.drop_index("ix_purchase_budget_alloc_owner_release", table_name="purchase_budget_allocation")
    op.drop_table("purchase_budget_allocation")
    op.drop_index("ix_purchase_budget_owner_active", table_name="purchase_budget")
    op.drop_table("purchase_budget")
