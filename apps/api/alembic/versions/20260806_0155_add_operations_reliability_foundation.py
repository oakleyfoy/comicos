"""add operations reliability foundation

Revision ID: 20260806_0155
Revises: 20260805_0154
Create Date: 2026-08-06 01:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260806_0155"
down_revision = "20260805_0154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_health_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_uuid", sa.String(length=64), nullable=False),
        sa.Column("subsystem", sa.String(length=80), nullable=False),
        sa.Column("health_status", sa.String(length=24), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False),
        sa.Column("check_payload_json", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("check_uuid", name="uq_platform_health_check_uuid"),
    )
    op.create_index("ix_platform_health_check_check_uuid", "platform_health_check", ["check_uuid"])
    op.create_index("ix_platform_health_check_subsystem", "platform_health_check", ["subsystem"])
    op.create_index("ix_platform_health_check_health_status", "platform_health_check", ["health_status"])
    op.create_index("ix_platform_health_check_checked_at", "platform_health_check", ["checked_at"])
    op.create_index("ix_platform_health_check_subsystem_checked", "platform_health_check", ["subsystem", "checked_at", "id"])

    op.create_table(
        "reliability_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_uuid", sa.String(length=64), nullable=False),
        sa.Column("subsystem", sa.String(length=80), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("issue_status", sa.String(length=24), nullable=False),
        sa.Column("issue_payload_json", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_uuid", name="uq_reliability_issue_uuid"),
    )
    op.create_index("ix_reliability_issue_issue_uuid", "reliability_issue", ["issue_uuid"])
    op.create_index("ix_reliability_issue_subsystem", "reliability_issue", ["subsystem"])
    op.create_index("ix_reliability_issue_issue_type", "reliability_issue", ["issue_type"])
    op.create_index("ix_reliability_issue_severity", "reliability_issue", ["severity"])
    op.create_index("ix_reliability_issue_issue_status", "reliability_issue", ["issue_status"])
    op.create_index("ix_reliability_issue_detected_at", "reliability_issue", ["detected_at"])
    op.create_index("ix_reliability_issue_subsystem_detected", "reliability_issue", ["subsystem", "detected_at", "id"])

    op.create_table(
        "job_health_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("total_jobs", sa.Integer(), nullable=False),
        sa.Column("successful_jobs", sa.Integer(), nullable=False),
        sa.Column("failed_jobs", sa.Integer(), nullable=False),
        sa.Column("average_duration_ms", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_health_metric_job_type", "job_health_metric", ["job_type"])
    op.create_index("ix_job_health_metric_measured_at", "job_health_metric", ["measured_at"])
    op.create_index("ix_job_health_metric_type_measured", "job_health_metric", ["job_type", "measured_at", "id"])

    op.create_table(
        "queue_health_metric",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("queue_name", sa.String(length=120), nullable=False),
        sa.Column("queued_count", sa.Integer(), nullable=False),
        sa.Column("running_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_health_metric_queue_name", "queue_health_metric", ["queue_name"])
    op.create_index("ix_queue_health_metric_measured_at", "queue_health_metric", ["measured_at"])
    op.create_index("ix_queue_health_metric_name_measured", "queue_health_metric", ["queue_name", "measured_at", "id"])

    op.create_table(
        "recovery_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("subsystem", sa.String(length=80), nullable=False),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_recovery_recommendation_uuid"),
    )
    op.create_index("ix_recovery_recommendation_recommendation_uuid", "recovery_recommendation", ["recommendation_uuid"])
    op.create_index("ix_recovery_recommendation_subsystem", "recovery_recommendation", ["subsystem"])
    op.create_index("ix_recovery_recommendation_recommendation_type", "recovery_recommendation", ["recommendation_type"])
    op.create_index("ix_recovery_recommendation_created_at", "recovery_recommendation", ["created_at"])
    op.create_index(
        "ix_recovery_recommendation_subsystem_created",
        "recovery_recommendation",
        ["subsystem", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recovery_recommendation_subsystem_created", table_name="recovery_recommendation")
    op.drop_index("ix_recovery_recommendation_created_at", table_name="recovery_recommendation")
    op.drop_index("ix_recovery_recommendation_recommendation_type", table_name="recovery_recommendation")
    op.drop_index("ix_recovery_recommendation_subsystem", table_name="recovery_recommendation")
    op.drop_index("ix_recovery_recommendation_recommendation_uuid", table_name="recovery_recommendation")
    op.drop_table("recovery_recommendation")

    op.drop_index("ix_queue_health_metric_name_measured", table_name="queue_health_metric")
    op.drop_index("ix_queue_health_metric_measured_at", table_name="queue_health_metric")
    op.drop_index("ix_queue_health_metric_queue_name", table_name="queue_health_metric")
    op.drop_table("queue_health_metric")

    op.drop_index("ix_job_health_metric_type_measured", table_name="job_health_metric")
    op.drop_index("ix_job_health_metric_measured_at", table_name="job_health_metric")
    op.drop_index("ix_job_health_metric_job_type", table_name="job_health_metric")
    op.drop_table("job_health_metric")

    op.drop_index("ix_reliability_issue_subsystem_detected", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_detected_at", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_issue_status", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_severity", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_issue_type", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_subsystem", table_name="reliability_issue")
    op.drop_index("ix_reliability_issue_issue_uuid", table_name="reliability_issue")
    op.drop_table("reliability_issue")

    op.drop_index("ix_platform_health_check_subsystem_checked", table_name="platform_health_check")
    op.drop_index("ix_platform_health_check_checked_at", table_name="platform_health_check")
    op.drop_index("ix_platform_health_check_health_status", table_name="platform_health_check")
    op.drop_index("ix_platform_health_check_subsystem", table_name="platform_health_check")
    op.drop_index("ix_platform_health_check_check_uuid", table_name="platform_health_check")
    op.drop_table("platform_health_check")
