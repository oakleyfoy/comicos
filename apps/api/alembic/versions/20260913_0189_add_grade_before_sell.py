from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_0189"
down_revision = "20260912_0188"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grade_before_sell_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=24), nullable=False),
        sa.Column("current_estimated_value", sa.Float(), nullable=False),
        sa.Column("expected_graded_value", sa.Float(), nullable=False),
        sa.Column("estimated_grading_cost", sa.Float(), nullable=False),
        sa.Column("expected_value_gain", sa.Float(), nullable=False),
        sa.Column("expected_roi", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grade_before_sell_owner_item",
        "grade_before_sell_recommendation",
        ["owner_user_id", "inventory_item_id", "created_at", "id"],
    )
    op.create_index(
        "ix_grade_before_sell_owner_rec",
        "grade_before_sell_recommendation",
        ["owner_user_id", "recommendation", "id"],
    )
    op.create_index(
        op.f("ix_grade_before_sell_recommendation_owner_user_id"),
        "grade_before_sell_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_grade_before_sell_recommendation_inventory_item_id"),
        "grade_before_sell_recommendation",
        ["inventory_item_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_grade_before_sell_recommendation_inventory_item_id"), table_name="grade_before_sell_recommendation")
    op.drop_index(op.f("ix_grade_before_sell_recommendation_owner_user_id"), table_name="grade_before_sell_recommendation")
    op.drop_index("ix_grade_before_sell_owner_rec", table_name="grade_before_sell_recommendation")
    op.drop_index("ix_grade_before_sell_owner_item", table_name="grade_before_sell_recommendation")
    op.drop_table("grade_before_sell_recommendation")
