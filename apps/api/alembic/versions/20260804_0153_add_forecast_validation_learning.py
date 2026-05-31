"""add forecast validation learning

Revision ID: 20260804_0153
Revises: 20260803_0152
Create Date: 2026-08-04 01:53:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260804_0153"
down_revision = "20260803_0152"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecast_validation_execution",
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
        sa.UniqueConstraint("execution_uuid", name="uq_forecast_validation_execution_uuid"),
    )
    op.create_index("ix_forecast_validation_execution_owner_user_id", "forecast_validation_execution", ["owner_user_id"])
    op.create_index("ix_forecast_validation_execution_agent_code", "forecast_validation_execution", ["agent_code"])
    op.create_index("ix_forecast_validation_execution_execution_uuid", "forecast_validation_execution", ["execution_uuid"])
    op.create_index("ix_forecast_validation_execution_status", "forecast_validation_execution", ["status"])
    op.create_index("ix_forecast_validation_execution_created_at", "forecast_validation_execution", ["created_at"])
    op.create_index("ix_forecast_validation_execution_owner_created", "forecast_validation_execution", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "forecast_validation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("validation_uuid", sa.String(length=64), nullable=False),
        sa.Column("forecast_id", sa.Integer(), nullable=False),
        sa.Column("validation_type", sa.String(length=80), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("variance_value", sa.Float(), nullable=False),
        sa.Column("variance_percent", sa.Float(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["forecast_id"], ["market_forecast.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("validation_uuid", name="uq_forecast_validation_uuid"),
    )
    op.create_index("ix_forecast_validation_owner_user_id", "forecast_validation", ["owner_user_id"])
    op.create_index("ix_forecast_validation_validation_uuid", "forecast_validation", ["validation_uuid"])
    op.create_index("ix_forecast_validation_forecast_id", "forecast_validation", ["forecast_id"])
    op.create_index("ix_forecast_validation_validation_type", "forecast_validation", ["validation_type"])
    op.create_index("ix_forecast_validation_validated_at", "forecast_validation", ["validated_at"])
    op.create_index("ix_forecast_validation_owner_validated", "forecast_validation", ["owner_user_id", "validated_at", "id"])

    op.create_table(
        "forecast_accuracy_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("forecast_type", sa.String(length=80), nullable=False),
        sa.Column("forecast_horizon_days", sa.Integer(), nullable=False),
        sa.Column("total_forecasts", sa.Integer(), nullable=False),
        sa.Column("average_error", sa.Float(), nullable=False),
        sa.Column("average_accuracy", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_accuracy_metric_owner_user_id", "forecast_accuracy_metric", ["owner_user_id"])
    op.create_index("ix_forecast_accuracy_metric_metric_date", "forecast_accuracy_metric", ["metric_date"])
    op.create_index("ix_forecast_accuracy_metric_forecast_type", "forecast_accuracy_metric", ["forecast_type"])
    op.create_index("ix_forecast_accuracy_metric_forecast_horizon_days", "forecast_accuracy_metric", ["forecast_horizon_days"])
    op.create_index("ix_forecast_accuracy_metric_created_at", "forecast_accuracy_metric", ["created_at"])
    op.create_index("ix_forecast_accuracy_metric_owner_date", "forecast_accuracy_metric", ["owner_user_id", "metric_date", "id"])

    op.create_table(
        "forecast_drift_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("event_uuid", sa.String(length=64), nullable=False),
        sa.Column("forecast_type", sa.String(length=80), nullable=False),
        sa.Column("drift_type", sa.String(length=80), nullable=False),
        sa.Column("drift_score", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid", name="uq_forecast_drift_event_uuid"),
    )
    op.create_index("ix_forecast_drift_event_owner_user_id", "forecast_drift_event", ["owner_user_id"])
    op.create_index("ix_forecast_drift_event_event_uuid", "forecast_drift_event", ["event_uuid"])
    op.create_index("ix_forecast_drift_event_forecast_type", "forecast_drift_event", ["forecast_type"])
    op.create_index("ix_forecast_drift_event_drift_type", "forecast_drift_event", ["drift_type"])
    op.create_index("ix_forecast_drift_event_detected_at", "forecast_drift_event", ["detected_at"])
    op.create_index("ix_forecast_drift_event_owner_detected", "forecast_drift_event", ["owner_user_id", "detected_at", "id"])

    op.create_table(
        "signal_quality_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("signal_source", sa.String(length=80), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False),
        sa.Column("consistency_score", sa.Float(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_quality_metric_owner_user_id", "signal_quality_metric", ["owner_user_id"])
    op.create_index("ix_signal_quality_metric_signal_type", "signal_quality_metric", ["signal_type"])
    op.create_index("ix_signal_quality_metric_signal_source", "signal_quality_metric", ["signal_source"])
    op.create_index("ix_signal_quality_metric_quality_score", "signal_quality_metric", ["quality_score"])
    op.create_index("ix_signal_quality_metric_measured_at", "signal_quality_metric", ["measured_at"])
    op.create_index("ix_signal_quality_metric_owner_measured", "signal_quality_metric", ["owner_user_id", "measured_at", "id"])

    op.create_table(
        "forecast_outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("outcome_uuid", sa.String(length=64), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("forecast_id", sa.Integer(), nullable=True),
        sa.Column("outcome_type", sa.String(length=80), nullable=False),
        sa.Column("outcome_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["forecast_id"], ["market_forecast.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["dealer_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_uuid", name="uq_forecast_outcome_uuid"),
    )
    op.create_index("ix_forecast_outcome_owner_user_id", "forecast_outcome", ["owner_user_id"])
    op.create_index("ix_forecast_outcome_outcome_uuid", "forecast_outcome", ["outcome_uuid"])
    op.create_index("ix_forecast_outcome_recommendation_id", "forecast_outcome", ["recommendation_id"])
    op.create_index("ix_forecast_outcome_forecast_id", "forecast_outcome", ["forecast_id"])
    op.create_index("ix_forecast_outcome_outcome_type", "forecast_outcome", ["outcome_type"])
    op.create_index("ix_forecast_outcome_created_at", "forecast_outcome", ["created_at"])
    op.create_index("ix_forecast_outcome_owner_created", "forecast_outcome", ["owner_user_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_forecast_outcome_owner_created", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_created_at", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_outcome_type", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_forecast_id", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_recommendation_id", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_outcome_uuid", table_name="forecast_outcome")
    op.drop_index("ix_forecast_outcome_owner_user_id", table_name="forecast_outcome")
    op.drop_table("forecast_outcome")

    op.drop_index("ix_signal_quality_metric_owner_measured", table_name="signal_quality_metric")
    op.drop_index("ix_signal_quality_metric_measured_at", table_name="signal_quality_metric")
    op.drop_index("ix_signal_quality_metric_quality_score", table_name="signal_quality_metric")
    op.drop_index("ix_signal_quality_metric_signal_source", table_name="signal_quality_metric")
    op.drop_index("ix_signal_quality_metric_signal_type", table_name="signal_quality_metric")
    op.drop_index("ix_signal_quality_metric_owner_user_id", table_name="signal_quality_metric")
    op.drop_table("signal_quality_metric")

    op.drop_index("ix_forecast_drift_event_owner_detected", table_name="forecast_drift_event")
    op.drop_index("ix_forecast_drift_event_detected_at", table_name="forecast_drift_event")
    op.drop_index("ix_forecast_drift_event_drift_type", table_name="forecast_drift_event")
    op.drop_index("ix_forecast_drift_event_forecast_type", table_name="forecast_drift_event")
    op.drop_index("ix_forecast_drift_event_event_uuid", table_name="forecast_drift_event")
    op.drop_index("ix_forecast_drift_event_owner_user_id", table_name="forecast_drift_event")
    op.drop_table("forecast_drift_event")

    op.drop_index("ix_forecast_accuracy_metric_owner_date", table_name="forecast_accuracy_metric")
    op.drop_index("ix_forecast_accuracy_metric_created_at", table_name="forecast_accuracy_metric")
    op.drop_index("ix_forecast_accuracy_metric_forecast_horizon_days", table_name="forecast_accuracy_metric")
    op.drop_index("ix_forecast_accuracy_metric_forecast_type", table_name="forecast_accuracy_metric")
    op.drop_index("ix_forecast_accuracy_metric_metric_date", table_name="forecast_accuracy_metric")
    op.drop_index("ix_forecast_accuracy_metric_owner_user_id", table_name="forecast_accuracy_metric")
    op.drop_table("forecast_accuracy_metric")

    op.drop_index("ix_forecast_validation_owner_validated", table_name="forecast_validation")
    op.drop_index("ix_forecast_validation_validated_at", table_name="forecast_validation")
    op.drop_index("ix_forecast_validation_validation_type", table_name="forecast_validation")
    op.drop_index("ix_forecast_validation_forecast_id", table_name="forecast_validation")
    op.drop_index("ix_forecast_validation_validation_uuid", table_name="forecast_validation")
    op.drop_index("ix_forecast_validation_owner_user_id", table_name="forecast_validation")
    op.drop_table("forecast_validation")

    op.drop_index("ix_forecast_validation_execution_owner_created", table_name="forecast_validation_execution")
    op.drop_index("ix_forecast_validation_execution_created_at", table_name="forecast_validation_execution")
    op.drop_index("ix_forecast_validation_execution_status", table_name="forecast_validation_execution")
    op.drop_index("ix_forecast_validation_execution_execution_uuid", table_name="forecast_validation_execution")
    op.drop_index("ix_forecast_validation_execution_agent_code", table_name="forecast_validation_execution")
    op.drop_index("ix_forecast_validation_execution_owner_user_id", table_name="forecast_validation_execution")
    op.drop_table("forecast_validation_execution")
