from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260917_0193"
down_revision = "20260916_0192"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cross_system_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("estimated_value", sa.Float(), nullable=True),
        sa.Column("recommendation_rank", sa.Integer(), nullable=False),
        sa.Column("source_systems", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cross_system_rec_owner_rank",
        "cross_system_recommendation",
        ["owner_user_id", "recommendation_rank", "created_at", "id"],
    )
    op.create_index(
        "ix_cross_system_rec_owner_created",
        "cross_system_recommendation",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_cross_system_recommendation_owner_user_id"),
        "cross_system_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_cross_system_recommendation_recommendation_type"),
        "cross_system_recommendation",
        ["recommendation_type"],
    )
    op.create_index(
        op.f("ix_cross_system_recommendation_recommendation_rank"),
        "cross_system_recommendation",
        ["recommendation_rank"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cross_system_recommendation_recommendation_rank"), table_name="cross_system_recommendation")
    op.drop_index(op.f("ix_cross_system_recommendation_recommendation_type"), table_name="cross_system_recommendation")
    op.drop_index(op.f("ix_cross_system_recommendation_owner_user_id"), table_name="cross_system_recommendation")
    op.drop_index("ix_cross_system_rec_owner_created", table_name="cross_system_recommendation")
    op.drop_index("ix_cross_system_rec_owner_rank", table_name="cross_system_recommendation")
    op.drop_table("cross_system_recommendation")
