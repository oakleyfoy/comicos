from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260916_0192"
down_revision = "20260915_0191"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unified_collector_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_systems", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_unified_collector_owner_type_title",
        "unified_collector_recommendation",
        ["owner_user_id", "recommendation_type", "title", "created_at", "id"],
    )
    op.create_index(
        "ix_unified_collector_owner_created",
        "unified_collector_recommendation",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_unified_collector_recommendation_owner_user_id"),
        "unified_collector_recommendation",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_unified_collector_recommendation_recommendation_type"),
        "unified_collector_recommendation",
        ["recommendation_type"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_unified_collector_recommendation_recommendation_type"),
        table_name="unified_collector_recommendation",
    )
    op.drop_index(
        op.f("ix_unified_collector_recommendation_owner_user_id"),
        table_name="unified_collector_recommendation",
    )
    op.drop_index("ix_unified_collector_owner_created", table_name="unified_collector_recommendation")
    op.drop_index("ix_unified_collector_owner_type_title", table_name="unified_collector_recommendation")
    op.drop_table("unified_collector_recommendation")
