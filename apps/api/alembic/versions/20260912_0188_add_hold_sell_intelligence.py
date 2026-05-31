from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260912_0188"
down_revision = "20260911_0187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hold_sell_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=8), nullable=False),
        sa.Column("conviction_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("estimated_fmv", sa.Float(), nullable=False),
        sa.Column("acquisition_cost", sa.Float(), nullable=False),
        sa.Column("unrealized_gain", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hold_sell_rec_owner_item",
        "hold_sell_recommendation",
        ["owner_user_id", "inventory_item_id", "created_at", "id"],
    )
    op.create_index("ix_hold_sell_rec_owner_rec", "hold_sell_recommendation", ["owner_user_id", "recommendation", "id"])
    op.create_index(op.f("ix_hold_sell_recommendation_owner_user_id"), "hold_sell_recommendation", ["owner_user_id"])
    op.create_index(op.f("ix_hold_sell_recommendation_inventory_item_id"), "hold_sell_recommendation", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_hold_sell_recommendation_inventory_item_id"), table_name="hold_sell_recommendation")
    op.drop_index(op.f("ix_hold_sell_recommendation_owner_user_id"), table_name="hold_sell_recommendation")
    op.drop_index("ix_hold_sell_rec_owner_rec", table_name="hold_sell_recommendation")
    op.drop_index("ix_hold_sell_rec_owner_item", table_name="hold_sell_recommendation")
    op.drop_table("hold_sell_recommendation")
