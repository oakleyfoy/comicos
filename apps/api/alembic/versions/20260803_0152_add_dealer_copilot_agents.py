"""add dealer copilot agents

Revision ID: 20260803_0152
Revises: 20260802_0151
Create Date: 2026-08-03 01:52:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260803_0152"
down_revision = "20260802_0151"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dealer_copilot_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_dealer_copilot_execution_uuid"),
    )
    op.create_index("ix_dealer_copilot_execution_owner_user_id", "dealer_copilot_execution", ["owner_user_id"])
    op.create_index("ix_dealer_copilot_execution_agent_code", "dealer_copilot_execution", ["agent_code"])
    op.create_index("ix_dealer_copilot_execution_execution_uuid", "dealer_copilot_execution", ["execution_uuid"])
    op.create_index("ix_dealer_copilot_execution_status", "dealer_copilot_execution", ["status"])
    op.create_index("ix_dealer_copilot_execution_created_at", "dealer_copilot_execution", ["created_at"])
    op.create_index("ix_dealer_copilot_execution_owner_created", "dealer_copilot_execution", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "dealer_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_execution_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("recommendation_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_execution_id"], ["dealer_copilot_execution.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_dealer_recommendation_uuid"),
    )
    op.create_index("ix_dealer_recommendation_owner_user_id", "dealer_recommendation", ["owner_user_id"])
    op.create_index("ix_dealer_recommendation_agent_execution_id", "dealer_recommendation", ["agent_execution_id"])
    op.create_index("ix_dealer_recommendation_recommendation_uuid", "dealer_recommendation", ["recommendation_uuid"])
    op.create_index("ix_dealer_recommendation_recommendation_type", "dealer_recommendation", ["recommendation_type"])
    op.create_index("ix_dealer_recommendation_asset_type", "dealer_recommendation", ["asset_type"])
    op.create_index("ix_dealer_recommendation_asset_id", "dealer_recommendation", ["asset_id"])
    op.create_index("ix_dealer_recommendation_recommendation_status", "dealer_recommendation", ["recommendation_status"])
    op.create_index("ix_dealer_recommendation_created_at", "dealer_recommendation", ["created_at"])
    op.create_index("ix_dealer_recommendation_owner_created", "dealer_recommendation", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "dealer_recommendation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("evidence_source", sa.String(length=160), nullable=False),
        sa.Column("evidence_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["dealer_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dealer_recommendation_evidence_recommendation_id", "dealer_recommendation_evidence", ["recommendation_id"])
    op.create_index("ix_dealer_recommendation_evidence_evidence_type", "dealer_recommendation_evidence", ["evidence_type"])
    op.create_index("ix_dealer_recommendation_evidence_created_at", "dealer_recommendation_evidence", ["created_at"])
    op.create_index("ix_dealer_recommendation_evidence_recommendation_created", "dealer_recommendation_evidence", ["recommendation_id", "created_at", "id"])

    op.create_table(
        "dealer_recommendation_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["recommendation_id"], ["dealer_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dealer_recommendation_review_recommendation_id", "dealer_recommendation_review", ["recommendation_id"])
    op.create_index("ix_dealer_recommendation_review_review_status", "dealer_recommendation_review", ["review_status"])
    op.create_index("ix_dealer_recommendation_review_reviewed_at", "dealer_recommendation_review", ["reviewed_at"])
    op.create_index("ix_dealer_recommendation_review_recommendation_reviewed", "dealer_recommendation_review", ["recommendation_id", "reviewed_at", "id"])

    op.create_table(
        "dealer_opportunity_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("forecast_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("grading_score", sa.Float(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dealer_opportunity_score_owner_user_id", "dealer_opportunity_score", ["owner_user_id"])
    op.create_index("ix_dealer_opportunity_score_asset_type", "dealer_opportunity_score", ["asset_type"])
    op.create_index("ix_dealer_opportunity_score_asset_id", "dealer_opportunity_score", ["asset_id"])
    op.create_index("ix_dealer_opportunity_score_opportunity_score", "dealer_opportunity_score", ["opportunity_score"])
    op.create_index("ix_dealer_opportunity_score_risk_score", "dealer_opportunity_score", ["risk_score"])
    op.create_index("ix_dealer_opportunity_score_calculated_at", "dealer_opportunity_score", ["calculated_at"])
    op.create_index("ix_dealer_opportunity_score_owner_calculated", "dealer_opportunity_score", ["owner_user_id", "calculated_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_dealer_opportunity_score_owner_calculated", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_calculated_at", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_risk_score", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_opportunity_score", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_asset_id", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_asset_type", table_name="dealer_opportunity_score")
    op.drop_index("ix_dealer_opportunity_score_owner_user_id", table_name="dealer_opportunity_score")
    op.drop_table("dealer_opportunity_score")

    op.drop_index("ix_dealer_recommendation_review_recommendation_reviewed", table_name="dealer_recommendation_review")
    op.drop_index("ix_dealer_recommendation_review_reviewed_at", table_name="dealer_recommendation_review")
    op.drop_index("ix_dealer_recommendation_review_review_status", table_name="dealer_recommendation_review")
    op.drop_index("ix_dealer_recommendation_review_recommendation_id", table_name="dealer_recommendation_review")
    op.drop_table("dealer_recommendation_review")

    op.drop_index("ix_dealer_recommendation_evidence_recommendation_created", table_name="dealer_recommendation_evidence")
    op.drop_index("ix_dealer_recommendation_evidence_created_at", table_name="dealer_recommendation_evidence")
    op.drop_index("ix_dealer_recommendation_evidence_evidence_type", table_name="dealer_recommendation_evidence")
    op.drop_index("ix_dealer_recommendation_evidence_recommendation_id", table_name="dealer_recommendation_evidence")
    op.drop_table("dealer_recommendation_evidence")

    op.drop_index("ix_dealer_recommendation_owner_created", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_created_at", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_recommendation_status", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_asset_id", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_asset_type", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_recommendation_type", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_recommendation_uuid", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_agent_execution_id", table_name="dealer_recommendation")
    op.drop_index("ix_dealer_recommendation_owner_user_id", table_name="dealer_recommendation")
    op.drop_table("dealer_recommendation")

    op.drop_index("ix_dealer_copilot_execution_owner_created", table_name="dealer_copilot_execution")
    op.drop_index("ix_dealer_copilot_execution_created_at", table_name="dealer_copilot_execution")
    op.drop_index("ix_dealer_copilot_execution_status", table_name="dealer_copilot_execution")
    op.drop_index("ix_dealer_copilot_execution_execution_uuid", table_name="dealer_copilot_execution")
    op.drop_index("ix_dealer_copilot_execution_agent_code", table_name="dealer_copilot_execution")
    op.drop_index("ix_dealer_copilot_execution_owner_user_id", table_name="dealer_copilot_execution")
    op.drop_table("dealer_copilot_execution")
