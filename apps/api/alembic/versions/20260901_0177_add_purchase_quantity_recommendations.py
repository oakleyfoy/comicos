from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260901_0177"
down_revision = "20260831_0176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_quantity_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_tier", sa.String(length=24), nullable=False),
        sa.Column("quantity_recommended", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_qty_rec_owner_release",
        "purchase_quantity_recommendation",
        ["owner_user_id", "release_id", "created_at", "id"],
    )
    op.create_index(
        "ix_purchase_qty_rec_owner_tier",
        "purchase_quantity_recommendation",
        ["owner_user_id", "recommendation_tier", "id"],
    )
    op.create_index(
        op.f("ix_purchase_quantity_recommendation_owner_user_id"),
        "purchase_quantity_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_purchase_quantity_recommendation_release_id"),
        "purchase_quantity_recommendation",
        ["release_id"],
    )
    op.create_index(
        op.f("ix_purchase_quantity_recommendation_recommendation_tier"),
        "purchase_quantity_recommendation",
        ["recommendation_tier"],
    )
    op.create_index(
        op.f("ix_purchase_quantity_recommendation_quantity_recommended"),
        "purchase_quantity_recommendation",
        ["quantity_recommended"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_purchase_quantity_recommendation_quantity_recommended"),
        table_name="purchase_quantity_recommendation",
    )
    op.drop_index(
        op.f("ix_purchase_quantity_recommendation_recommendation_tier"),
        table_name="purchase_quantity_recommendation",
    )
    op.drop_index(
        op.f("ix_purchase_quantity_recommendation_release_id"),
        table_name="purchase_quantity_recommendation",
    )
    op.drop_index(
        op.f("ix_purchase_quantity_recommendation_owner_user_id"),
        table_name="purchase_quantity_recommendation",
    )
    op.drop_index("ix_purchase_qty_rec_owner_tier", table_name="purchase_quantity_recommendation")
    op.drop_index("ix_purchase_qty_rec_owner_release", table_name="purchase_quantity_recommendation")
    op.drop_table("purchase_quantity_recommendation")
