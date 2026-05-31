"""add spec intelligence

Revision ID: 20260813_0162
Revises: 20260812_0161
Create Date: 2026-08-13 02:02:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260813_0162"
down_revision = "20260812_0161"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("score_grade", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("score_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spec_score_release_issue_id", "spec_score", ["release_issue_id"])
    op.create_index("ix_spec_score_score_value", "spec_score", ["score_value"])
    op.create_index("ix_spec_score_score_grade", "spec_score", ["score_grade"])
    op.create_index("ix_spec_score_confidence_score", "spec_score", ["confidence_score"])
    op.create_index("ix_spec_score_created_at", "spec_score", ["created_at"])
    op.create_index("ix_spec_score_issue_created", "spec_score", ["release_issue_id", "created_at", "id"])
    op.create_index("ix_spec_score_value_created", "spec_score", ["score_value", "created_at", "id"])

    op.create_table(
        "spec_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=24), nullable=False),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("recommendation_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_spec_recommendation_uuid"),
    )
    op.create_index("ix_spec_recommendation_recommendation_uuid", "spec_recommendation", ["recommendation_uuid"])
    op.create_index("ix_spec_recommendation_release_issue_id", "spec_recommendation", ["release_issue_id"])
    op.create_index("ix_spec_recommendation_recommendation_type", "spec_recommendation", ["recommendation_type"])
    op.create_index("ix_spec_recommendation_created_at", "spec_recommendation", ["created_at"])
    op.create_index(
        "ix_spec_recommendation_issue_created", "spec_recommendation", ["release_issue_id", "created_at", "id"]
    )
    op.create_index(
        "ix_spec_recommendation_type_created", "spec_recommendation", ["recommendation_type", "created_at", "id"]
    )

    op.create_table(
        "spec_recommendation_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["spec_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spec_recommendation_review_recommendation_id", "spec_recommendation_review", ["recommendation_id"])
    op.create_index("ix_spec_recommendation_review_review_status", "spec_recommendation_review", ["review_status"])
    op.create_index("ix_spec_recommendation_review_rec_created", "spec_recommendation_review", ["recommendation_id", "reviewed_at", "id"])

    op.create_table(
        "weekly_buy_list",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("list_uuid", sa.String(length=64), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("list_uuid", name="uq_weekly_buy_list_uuid"),
    )
    op.create_index("ix_weekly_buy_list_owner_user_id", "weekly_buy_list", ["owner_user_id"])
    op.create_index("ix_weekly_buy_list_list_uuid", "weekly_buy_list", ["list_uuid"])
    op.create_index("ix_weekly_buy_list_week_start_date", "weekly_buy_list", ["week_start_date"])
    op.create_index("ix_weekly_buy_list_owner_week", "weekly_buy_list", ["owner_user_id", "week_start_date", "id"])

    op.create_table(
        "weekly_buy_list_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("weekly_buy_list_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("buy_category", sa.String(length=24), nullable=False),
        sa.Column("ranking_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["weekly_buy_list_id"], ["weekly_buy_list.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weekly_buy_list_item_weekly_buy_list_id", "weekly_buy_list_item", ["weekly_buy_list_id"])
    op.create_index("ix_weekly_buy_list_item_release_issue_id", "weekly_buy_list_item", ["release_issue_id"])
    op.create_index("ix_weekly_buy_list_item_buy_category", "weekly_buy_list_item", ["buy_category"])
    op.create_index("ix_weekly_buy_list_item_created_at", "weekly_buy_list_item", ["created_at"])
    op.create_index(
        "ix_weekly_buy_list_item_list_rank", "weekly_buy_list_item", ["weekly_buy_list_id", "ranking_score", "id"]
    )

    op.create_table(
        "spec_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_spec_agent_execution_uuid"),
    )
    op.create_index("ix_spec_agent_execution_owner_user_id", "spec_agent_execution", ["owner_user_id"])
    op.create_index("ix_spec_agent_execution_agent_code", "spec_agent_execution", ["agent_code"])
    op.create_index("ix_spec_agent_execution_execution_uuid", "spec_agent_execution", ["execution_uuid"])
    op.create_index("ix_spec_agent_execution_status", "spec_agent_execution", ["status"])
    op.create_index("ix_spec_agent_execution_created_at", "spec_agent_execution", ["created_at"])
    op.create_index("ix_spec_agent_execution_owner_started", "spec_agent_execution", ["owner_user_id", "started_at", "id"])
    op.create_index("ix_spec_agent_execution_agent_started", "spec_agent_execution", ["agent_code", "started_at", "id"])


def downgrade() -> None:
    op.drop_table("spec_agent_execution")
    op.drop_table("weekly_buy_list_item")
    op.drop_table("weekly_buy_list")
    op.drop_table("spec_recommendation_review")
    op.drop_table("spec_recommendation")
    op.drop_table("spec_score")
