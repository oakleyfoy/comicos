from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260904_0180"
down_revision = "20260903_0179"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sell_candidate_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("estimated_fmv", sa.Float(), nullable=False),
        sa.Column("estimated_profit", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sell_candidate_rec_owner_item",
        "sell_candidate_recommendation",
        ["owner_user_id", "inventory_item_id", "created_at", "id"],
    )
    op.create_index(
        "ix_sell_candidate_rec_owner_rec",
        "sell_candidate_recommendation",
        ["owner_user_id", "recommendation", "id"],
    )
    op.create_index(
        op.f("ix_sell_candidate_recommendation_owner_user_id"),
        "sell_candidate_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_sell_candidate_recommendation_inventory_item_id"),
        "sell_candidate_recommendation",
        ["inventory_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sell_candidate_recommendation_inventory_item_id"),
        table_name="sell_candidate_recommendation",
    )
    op.drop_index(
        op.f("ix_sell_candidate_recommendation_owner_user_id"),
        table_name="sell_candidate_recommendation",
    )
    op.drop_index("ix_sell_candidate_rec_owner_rec", table_name="sell_candidate_recommendation")
    op.drop_index("ix_sell_candidate_rec_owner_item", table_name="sell_candidate_recommendation")
    op.drop_table("sell_candidate_recommendation")
