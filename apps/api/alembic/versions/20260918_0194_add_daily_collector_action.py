from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260918_0194"
down_revision = "20260917_0193"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_collector_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_recommendation_id", sa.Integer(), nullable=True),
        sa.Column("source_systems", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_collector_action_owner_type_title",
        "daily_collector_action",
        ["owner_user_id", "action_type", "title", "created_at", "id"],
    )
    op.create_index(
        "ix_daily_collector_action_owner_created",
        "daily_collector_action",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_daily_collector_action_owner_due",
        "daily_collector_action",
        ["owner_user_id", "due_date", "id"],
    )
    op.create_index(
        op.f("ix_daily_collector_action_owner_user_id"),
        "daily_collector_action",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_daily_collector_action_action_type"),
        "daily_collector_action",
        ["action_type"],
    )
    op.create_index(
        op.f("ix_daily_collector_action_source_recommendation_id"),
        "daily_collector_action",
        ["source_recommendation_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_collector_action_source_recommendation_id"), table_name="daily_collector_action")
    op.drop_index(op.f("ix_daily_collector_action_action_type"), table_name="daily_collector_action")
    op.drop_index(op.f("ix_daily_collector_action_owner_user_id"), table_name="daily_collector_action")
    op.drop_index("ix_daily_collector_action_owner_due", table_name="daily_collector_action")
    op.drop_index("ix_daily_collector_action_owner_created", table_name="daily_collector_action")
    op.drop_index("ix_daily_collector_action_owner_type_title", table_name="daily_collector_action")
    op.drop_table("daily_collector_action")
