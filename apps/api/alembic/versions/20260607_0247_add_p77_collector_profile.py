"""add p77 collector profile foundation

Revision ID: 20260607_0247
Revises: 20260607_0246
Create Date: 2026-06-07 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0247"
down_revision = "20260607_0246"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p77_collector_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("collector_type", sa.String(length=32), nullable=False),
        sa.Column("risk_profile", sa.String(length=32), nullable=False),
        sa.Column("time_horizon", sa.String(length=32), nullable=False),
        sa.Column("grading_preference", sa.String(length=32), nullable=False),
        sa.Column("hold_preference", sa.String(length=32), nullable=False),
        sa.Column("default_copy_count", sa.Integer(), nullable=False),
        sa.Column("key_issue_copy_count", sa.Integer(), nullable=False),
        sa.Column("ratio_variant_copy_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_p77_collector_profile_owner"),
    )
    op.create_index(op.f("ix_p77_collector_profile_owner_user_id"), "p77_collector_profile", ["owner_user_id"])

    op.create_table(
        "p77_collector_interest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("interest_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p77_interest_owner_type_rank", "p77_collector_interest", ["owner_user_id", "interest_type", "priority_rank", "id"])
    op.create_index(op.f("ix_p77_collector_interest_owner_user_id"), "p77_collector_interest", ["owner_user_id"])
    op.create_index(op.f("ix_p77_collector_interest_interest_type"), "p77_collector_interest", ["interest_type"])

    op.create_table(
        "p77_collector_goal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("goal_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("progress_value", sa.Float(), nullable=False),
        sa.Column("completion_percent", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p77_goal_owner_type", "p77_collector_goal", ["owner_user_id", "goal_type", "id"])
    op.create_index(op.f("ix_p77_collector_goal_owner_user_id"), "p77_collector_goal", ["owner_user_id"])
    op.create_index(op.f("ix_p77_collector_goal_goal_type"), "p77_collector_goal", ["goal_type"])

    op.create_table(
        "p77_collector_budget",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("monthly_budget", sa.Float(), nullable=False),
        sa.Column("budget_period", sa.String(length=16), nullable=False),
        sa.Column("publisher_allocations_json", sa.JSON(), nullable=False),
        sa.Column("category_allocations_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_p77_collector_budget_owner"),
    )
    op.create_index(op.f("ix_p77_collector_budget_owner_user_id"), "p77_collector_budget", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p77_collector_budget_owner_user_id"), table_name="p77_collector_budget")
    op.drop_table("p77_collector_budget")
    op.drop_index(op.f("ix_p77_collector_goal_goal_type"), table_name="p77_collector_goal")
    op.drop_index(op.f("ix_p77_collector_goal_owner_user_id"), table_name="p77_collector_goal")
    op.drop_index("ix_p77_goal_owner_type", table_name="p77_collector_goal")
    op.drop_table("p77_collector_goal")
    op.drop_index(op.f("ix_p77_collector_interest_interest_type"), table_name="p77_collector_interest")
    op.drop_index(op.f("ix_p77_collector_interest_owner_user_id"), table_name="p77_collector_interest")
    op.drop_index("ix_p77_interest_owner_type_rank", table_name="p77_collector_interest")
    op.drop_table("p77_collector_interest")
    op.drop_index(op.f("ix_p77_collector_profile_owner_user_id"), table_name="p77_collector_profile")
    op.drop_table("p77_collector_profile")
