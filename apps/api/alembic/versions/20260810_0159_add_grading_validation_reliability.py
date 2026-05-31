"""add grading validation reliability

Revision ID: 20260810_0159
Revises: 20260809_0158
Create Date: 2026-08-10 01:59:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0159"
down_revision = "20260809_0158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grade_validation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("validation_uuid", sa.String(length=64), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("actual_grade", sa.String(length=16), nullable=False),
        sa.Column("predicted_grade", sa.String(length=16), nullable=False),
        sa.Column("variance", sa.Float(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["grade_prediction.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("validation_uuid", name="uq_grade_validation_uuid"),
    )
    op.create_index("ix_grade_validation_owner_user_id", "grade_validation", ["owner_user_id"])
    op.create_index("ix_grade_validation_validation_uuid", "grade_validation", ["validation_uuid"])
    op.create_index("ix_grade_validation_prediction_id", "grade_validation", ["prediction_id"])
    op.create_index("ix_grade_validation_owner_validated", "grade_validation", ["owner_user_id", "validated_at", "id"])
    op.create_index(
        "ix_grade_validation_prediction_validated", "grade_validation", ["prediction_id", "validated_at", "id"]
    )

    op.create_table(
        "grade_calibration_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("grading_scale", sa.String(length=24), nullable=False),
        sa.Column("total_predictions", sa.Integer(), nullable=False),
        sa.Column("average_variance", sa.Float(), nullable=False),
        sa.Column("accuracy_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grade_calibration_metric_owner_user_id", "grade_calibration_metric", ["owner_user_id"])
    op.create_index("ix_grade_calibration_metric_metric_date", "grade_calibration_metric", ["metric_date"])
    op.create_index("ix_grade_calibration_metric_grading_scale", "grade_calibration_metric", ["grading_scale"])
    op.create_index("ix_grade_calibration_metric_accuracy_score", "grade_calibration_metric", ["accuracy_score"])
    op.create_index("ix_grade_calibration_metric_created_at", "grade_calibration_metric", ["created_at"])
    op.create_index(
        "ix_grade_calibration_metric_scale_accuracy",
        "grade_calibration_metric",
        ["grading_scale", "accuracy_score", "id"],
    )
    op.create_index(
        "ix_grade_calibration_metric_owner_created",
        "grade_calibration_metric",
        ["owner_user_id", "created_at", "id"],
    )

    op.create_table(
        "grade_prediction_outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("outcome_uuid", sa.String(length=64), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("prediction_id", sa.Integer(), nullable=True),
        sa.Column("outcome_type", sa.String(length=48), nullable=False),
        sa.Column("outcome_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["grading_intelligence_recommendation.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["grade_prediction.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_uuid", name="uq_grade_prediction_outcome_uuid"),
    )
    op.create_index("ix_grade_prediction_outcome_owner_user_id", "grade_prediction_outcome", ["owner_user_id"])
    op.create_index("ix_grade_prediction_outcome_outcome_uuid", "grade_prediction_outcome", ["outcome_uuid"])
    op.create_index("ix_grade_prediction_outcome_recommendation_id", "grade_prediction_outcome", ["recommendation_id"])
    op.create_index("ix_grade_prediction_outcome_prediction_id", "grade_prediction_outcome", ["prediction_id"])
    op.create_index("ix_grade_prediction_outcome_outcome_type", "grade_prediction_outcome", ["outcome_type"])
    op.create_index("ix_grade_prediction_outcome_created_at", "grade_prediction_outcome", ["created_at"])
    op.create_index(
        "ix_grade_prediction_outcome_owner_created",
        "grade_prediction_outcome",
        ["owner_user_id", "created_at", "id"],
    )

    op.create_table(
        "grading_drift_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("event_uuid", sa.String(length=64), nullable=False),
        sa.Column("drift_type", sa.String(length=48), nullable=False),
        sa.Column("drift_score", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid", name="uq_grading_drift_event_uuid"),
    )
    op.create_index("ix_grading_drift_event_owner_user_id", "grading_drift_event", ["owner_user_id"])
    op.create_index("ix_grading_drift_event_event_uuid", "grading_drift_event", ["event_uuid"])
    op.create_index("ix_grading_drift_event_drift_type", "grading_drift_event", ["drift_type"])
    op.create_index("ix_grading_drift_event_type_detected", "grading_drift_event", ["drift_type", "detected_at", "id"])
    op.create_index(
        "ix_grading_drift_event_owner_detected", "grading_drift_event", ["owner_user_id", "detected_at", "id"]
    )

    op.create_table(
        "grading_reliability_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("metric_uuid", sa.String(length=64), nullable=False),
        sa.Column("reliability_type", sa.String(length=48), nullable=False),
        sa.Column("metric_score", sa.Float(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_uuid", name="uq_grading_reliability_metric_uuid"),
    )
    op.create_index("ix_grading_reliability_metric_owner_user_id", "grading_reliability_metric", ["owner_user_id"])
    op.create_index("ix_grading_reliability_metric_metric_uuid", "grading_reliability_metric", ["metric_uuid"])
    op.create_index("ix_grading_reliability_metric_reliability_type", "grading_reliability_metric", ["reliability_type"])
    op.create_index(
        "ix_grading_reliability_metric_owner_measured",
        "grading_reliability_metric",
        ["owner_user_id", "measured_at", "id"],
    )

    op.create_table(
        "grading_validation_execution",
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
        sa.UniqueConstraint("execution_uuid", name="uq_grading_validation_execution_uuid"),
    )
    op.create_index("ix_grading_validation_execution_owner_user_id", "grading_validation_execution", ["owner_user_id"])
    op.create_index("ix_grading_validation_execution_agent_code", "grading_validation_execution", ["agent_code"])
    op.create_index("ix_grading_validation_execution_execution_uuid", "grading_validation_execution", ["execution_uuid"])
    op.create_index("ix_grading_validation_execution_status", "grading_validation_execution", ["status"])
    op.create_index("ix_grading_validation_execution_created_at", "grading_validation_execution", ["created_at"])
    op.create_index(
        "ix_grading_validation_execution_owner_started",
        "grading_validation_execution",
        ["owner_user_id", "started_at", "id"],
    )
    op.create_index(
        "ix_grading_validation_execution_agent_started",
        "grading_validation_execution",
        ["agent_code", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("grading_validation_execution")
    op.drop_table("grading_reliability_metric")
    op.drop_table("grading_drift_event")
    op.drop_table("grade_prediction_outcome")
    op.drop_table("grade_calibration_metric")
    op.drop_table("grade_validation")
