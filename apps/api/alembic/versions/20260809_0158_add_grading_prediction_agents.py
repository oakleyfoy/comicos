"""add grading prediction agents foundation

Revision ID: 20260809_0158
Revises: 20260808_0157
Create Date: 2026-08-09 01:58:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260809_0158"
down_revision = "20260808_0157"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grade_prediction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("prediction_uuid", sa.String(length=64), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("grading_scale", sa.String(length=24), nullable=False),
        sa.Column("predicted_grade", sa.String(length=16), nullable=False),
        sa.Column("grade_floor", sa.String(length=16), nullable=False),
        sa.Column("grade_ceiling", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prediction_uuid", name="uq_grade_prediction_uuid"),
    )
    op.create_index("ix_grade_prediction_owner_user_id", "grade_prediction", ["owner_user_id"])
    op.create_index("ix_grade_prediction_prediction_uuid", "grade_prediction", ["prediction_uuid"])
    op.create_index("ix_grade_prediction_analysis_id", "grade_prediction", ["analysis_id"])
    op.create_index("ix_grade_prediction_inventory_copy_id", "grade_prediction", ["inventory_copy_id"])
    op.create_index("ix_grade_prediction_grading_scale", "grade_prediction", ["grading_scale"])
    op.create_index("ix_grade_prediction_predicted_grade", "grade_prediction", ["predicted_grade"])
    op.create_index("ix_grade_prediction_confidence_score", "grade_prediction", ["confidence_score"])
    op.create_index("ix_grade_prediction_created_at", "grade_prediction", ["created_at"])
    op.create_index("ix_grade_prediction_owner_created", "grade_prediction", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_grade_prediction_scale_grade", "grade_prediction", ["grading_scale", "predicted_grade", "id"])

    op.create_table(
        "grade_prediction_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("evidence_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prediction_id"], ["grade_prediction.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grade_prediction_evidence_prediction_id", "grade_prediction_evidence", ["prediction_id"])
    op.create_index("ix_grade_prediction_evidence_evidence_type", "grade_prediction_evidence", ["evidence_type"])
    op.create_index("ix_grade_prediction_evidence_created_at", "grade_prediction_evidence", ["created_at"])
    op.create_index(
        "ix_grade_prediction_evidence_prediction_created",
        "grade_prediction_evidence",
        ["prediction_id", "created_at", "id"],
    )

    op.create_table(
        "grading_intelligence_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("recommendation_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["grade_prediction.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_grading_intelligence_recommendation_uuid"),
    )
    op.create_index("ix_grading_intelligence_recommendation_owner_user_id", "grading_intelligence_recommendation", ["owner_user_id"])
    op.create_index("ix_grading_intelligence_recommendation_recommendation_uuid", "grading_intelligence_recommendation", ["recommendation_uuid"])
    op.create_index("ix_grading_intelligence_recommendation_prediction_id", "grading_intelligence_recommendation", ["prediction_id"])
    op.create_index("ix_grading_intelligence_recommendation_inventory_copy_id", "grading_intelligence_recommendation", ["inventory_copy_id"])
    op.create_index("ix_grading_intelligence_recommendation_recommendation_type", "grading_intelligence_recommendation", ["recommendation_type"])
    op.create_index("ix_grading_intelligence_recommendation_recommendation_status", "grading_intelligence_recommendation", ["recommendation_status"])
    op.create_index("ix_grading_intelligence_recommendation_confidence_score", "grading_intelligence_recommendation", ["confidence_score"])
    op.create_index("ix_grading_intelligence_recommendation_priority_score", "grading_intelligence_recommendation", ["priority_score"])
    op.create_index("ix_grading_intelligence_recommendation_created_at", "grading_intelligence_recommendation", ["created_at"])
    op.create_index("ix_grading_intelligence_recommendation_owner_created", "grading_intelligence_recommendation", ["owner_user_id", "created_at", "id"])
    op.create_index(
        "ix_grading_intelligence_recommendation_type_status",
        "grading_intelligence_recommendation",
        ["recommendation_type", "recommendation_status", "id"],
    )

    op.create_table(
        "grading_intelligence_recommendation_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["grading_intelligence_recommendation.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grading_intelligence_recommendation_review_recommendation_id", "grading_intelligence_recommendation_review", ["recommendation_id"])
    op.create_index("ix_grading_intelligence_recommendation_review_review_status", "grading_intelligence_recommendation_review", ["review_status"])
    op.create_index("ix_grading_intelligence_recommendation_review_reviewed_by", "grading_intelligence_recommendation_review", ["reviewed_by"])
    op.create_index(
        "ix_grading_intelligence_recommendation_review_rec_created",
        "grading_intelligence_recommendation_review",
        ["recommendation_id", "reviewed_at", "id"],
    )

    op.create_table(
        "grading_intelligence_roi_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("raw_value", sa.Float(), nullable=False),
        sa.Column("expected_graded_value", sa.Float(), nullable=False),
        sa.Column("grading_cost", sa.Float(), nullable=False),
        sa.Column("expected_profit", sa.Float(), nullable=False),
        sa.Column("expected_roi_percent", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["grading_intelligence_recommendation.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grading_intelligence_roi_analysis_owner_user_id", "grading_intelligence_roi_analysis", ["owner_user_id"])
    op.create_index("ix_grading_intelligence_roi_analysis_recommendation_id", "grading_intelligence_roi_analysis", ["recommendation_id"])
    op.create_index("ix_grading_intelligence_roi_analysis_inventory_copy_id", "grading_intelligence_roi_analysis", ["inventory_copy_id"])
    op.create_index("ix_grading_intelligence_roi_analysis_created_at", "grading_intelligence_roi_analysis", ["created_at"])
    op.create_index("ix_grading_intelligence_roi_analysis_owner_created", "grading_intelligence_roi_analysis", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "grading_intelligence_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analysis.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_grading_intelligence_agent_execution_uuid"),
    )
    op.create_index("ix_grading_intelligence_agent_execution_owner_user_id", "grading_intelligence_agent_execution", ["owner_user_id"])
    op.create_index("ix_grading_intelligence_agent_execution_analysis_id", "grading_intelligence_agent_execution", ["analysis_id"])
    op.create_index("ix_grading_intelligence_agent_execution_agent_code", "grading_intelligence_agent_execution", ["agent_code"])
    op.create_index("ix_grading_intelligence_agent_execution_execution_uuid", "grading_intelligence_agent_execution", ["execution_uuid"])
    op.create_index("ix_grading_intelligence_agent_execution_status", "grading_intelligence_agent_execution", ["status"])
    op.create_index("ix_grading_intelligence_agent_execution_created_at", "grading_intelligence_agent_execution", ["created_at"])
    op.create_index(
        "ix_grading_intelligence_agent_execution_owner_started",
        "grading_intelligence_agent_execution",
        ["owner_user_id", "started_at", "id"],
    )
    op.create_index(
        "ix_grading_intelligence_agent_execution_agent_started",
        "grading_intelligence_agent_execution",
        ["agent_code", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_grading_intelligence_agent_execution_agent_started", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_owner_started", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_created_at", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_status", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_execution_uuid", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_agent_code", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_analysis_id", table_name="grading_intelligence_agent_execution")
    op.drop_index("ix_grading_intelligence_agent_execution_owner_user_id", table_name="grading_intelligence_agent_execution")
    op.drop_table("grading_intelligence_agent_execution")

    op.drop_index("ix_grading_intelligence_roi_analysis_owner_created", table_name="grading_intelligence_roi_analysis")
    op.drop_index("ix_grading_intelligence_roi_analysis_created_at", table_name="grading_intelligence_roi_analysis")
    op.drop_index("ix_grading_intelligence_roi_analysis_inventory_copy_id", table_name="grading_intelligence_roi_analysis")
    op.drop_index("ix_grading_intelligence_roi_analysis_recommendation_id", table_name="grading_intelligence_roi_analysis")
    op.drop_index("ix_grading_intelligence_roi_analysis_owner_user_id", table_name="grading_intelligence_roi_analysis")
    op.drop_table("grading_intelligence_roi_analysis")

    op.drop_index("ix_grading_intelligence_recommendation_review_rec_created", table_name="grading_intelligence_recommendation_review")
    op.drop_index("ix_grading_intelligence_recommendation_review_reviewed_by", table_name="grading_intelligence_recommendation_review")
    op.drop_index("ix_grading_intelligence_recommendation_review_review_status", table_name="grading_intelligence_recommendation_review")
    op.drop_index("ix_grading_intelligence_recommendation_review_recommendation_id", table_name="grading_intelligence_recommendation_review")
    op.drop_table("grading_intelligence_recommendation_review")

    op.drop_index("ix_grading_intelligence_recommendation_type_status", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_owner_created", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_created_at", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_priority_score", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_confidence_score", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_recommendation_status", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_recommendation_type", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_inventory_copy_id", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_prediction_id", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_recommendation_uuid", table_name="grading_intelligence_recommendation")
    op.drop_index("ix_grading_intelligence_recommendation_owner_user_id", table_name="grading_intelligence_recommendation")
    op.drop_table("grading_intelligence_recommendation")

    op.drop_index("ix_grade_prediction_evidence_prediction_created", table_name="grade_prediction_evidence")
    op.drop_index("ix_grade_prediction_evidence_created_at", table_name="grade_prediction_evidence")
    op.drop_index("ix_grade_prediction_evidence_evidence_type", table_name="grade_prediction_evidence")
    op.drop_index("ix_grade_prediction_evidence_prediction_id", table_name="grade_prediction_evidence")
    op.drop_table("grade_prediction_evidence")

    op.drop_index("ix_grade_prediction_scale_grade", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_owner_created", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_created_at", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_confidence_score", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_predicted_grade", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_grading_scale", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_inventory_copy_id", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_analysis_id", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_prediction_uuid", table_name="grade_prediction")
    op.drop_index("ix_grade_prediction_owner_user_id", table_name="grade_prediction")
    op.drop_table("grade_prediction")
