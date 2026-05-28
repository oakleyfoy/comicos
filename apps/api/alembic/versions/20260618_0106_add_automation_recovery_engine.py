"""add automation recovery engine

Revision ID: 20260618_0106
Revises: 20260617_0105
Create Date: 2026-06-18 00:10:06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260618_0106"
down_revision = "20260617_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_retry_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_key", sa.String(length=120), nullable=False),
        sa.Column("policy_name", sa.String(length=160), nullable=False),
        sa.Column("retry_mode", sa.String(length=32), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("base_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("max_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("deterministic_backoff_enabled", sa.Boolean(), nullable=False),
        sa.Column("dead_letter_enabled", sa.Boolean(), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_key", name="uq_automation_retry_policy_key"),
    )
    op.create_index("ix_automation_retry_policy_mode_created", "automation_retry_policies", ["retry_mode", "created_at", "id"])
    op.create_index(op.f("ix_automation_retry_policies_policy_key"), "automation_retry_policies", ["policy_key"])
    op.create_index(op.f("ix_automation_retry_policies_retry_mode"), "automation_retry_policies", ["retry_mode"])
    op.create_index(op.f("ix_automation_retry_policies_policy_checksum"), "automation_retry_policies", ["policy_checksum"])

    op.create_table(
        "automation_recovery_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("worker_execution_id", sa.Integer(), nullable=True),
        sa.Column("retry_policy_id", sa.Integer(), nullable=True),
        sa.Column("recovery_status", sa.String(length=24), nullable=False),
        sa.Column("recovery_type", sa.String(length=32), nullable=False),
        sa.Column("recovery_rank", sa.Integer(), nullable=False),
        sa.Column("recovery_checksum", sa.String(length=64), nullable=False),
        sa.Column("recovery_manifest_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["retry_policy_id"], ["automation_retry_policies.id"]),
        sa.ForeignKeyConstraint(["worker_execution_id"], ["automation_worker_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recovery_checksum", name="uq_automation_recovery_run_checksum"),
    )
    op.create_index("ix_automation_recovery_run_job_created", "automation_recovery_runs", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_recovery_run_status_created", "automation_recovery_runs", ["recovery_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_recovery_runs_owner_user_id"), "automation_recovery_runs", ["owner_user_id"])
    op.create_index(op.f("ix_automation_recovery_runs_organization_id"), "automation_recovery_runs", ["organization_id"])
    op.create_index(op.f("ix_automation_recovery_runs_job_id"), "automation_recovery_runs", ["job_id"])
    op.create_index(op.f("ix_automation_recovery_runs_worker_execution_id"), "automation_recovery_runs", ["worker_execution_id"])
    op.create_index(op.f("ix_automation_recovery_runs_retry_policy_id"), "automation_recovery_runs", ["retry_policy_id"])
    op.create_index(op.f("ix_automation_recovery_runs_recovery_status"), "automation_recovery_runs", ["recovery_status"])
    op.create_index(op.f("ix_automation_recovery_runs_recovery_type"), "automation_recovery_runs", ["recovery_type"])
    op.create_index(op.f("ix_automation_recovery_runs_recovery_rank"), "automation_recovery_runs", ["recovery_rank"])
    op.create_index(op.f("ix_automation_recovery_runs_recovery_checksum"), "automation_recovery_runs", ["recovery_checksum"])

    op.create_table(
        "automation_dead_letter_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_job_id", sa.Integer(), nullable=False),
        sa.Column("dead_letter_reason", sa.String(length=1024), nullable=False),
        sa.Column("dead_letter_status", sa.String(length=24), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("dead_letter_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["original_job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("original_job_id", name="uq_automation_dead_letter_original_job"),
    )
    op.create_index("ix_automation_dead_letter_status_created", "automation_dead_letter_jobs", ["dead_letter_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_dead_letter_jobs_original_job_id"), "automation_dead_letter_jobs", ["original_job_id"])
    op.create_index(op.f("ix_automation_dead_letter_jobs_dead_letter_status"), "automation_dead_letter_jobs", ["dead_letter_status"])
    op.create_index(op.f("ix_automation_dead_letter_jobs_source_checksum"), "automation_dead_letter_jobs", ["source_checksum"])
    op.create_index(op.f("ix_automation_dead_letter_jobs_dead_letter_checksum"), "automation_dead_letter_jobs", ["dead_letter_checksum"])

    op.create_table(
        "automation_failure_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("worker_execution_id", sa.Integer(), nullable=True),
        sa.Column("failure_type", sa.String(length=64), nullable=False),
        sa.Column("failure_severity", sa.String(length=16), nullable=False),
        sa.Column("failure_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("failure_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["worker_execution_id"], ["automation_worker_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("failure_checksum", name="uq_automation_failure_event_checksum"),
    )
    op.create_index("ix_automation_failure_event_job_created", "automation_failure_events", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_failure_event_severity_created", "automation_failure_events", ["failure_severity", "created_at", "id"])
    op.create_index(op.f("ix_automation_failure_events_job_id"), "automation_failure_events", ["job_id"])
    op.create_index(op.f("ix_automation_failure_events_worker_execution_id"), "automation_failure_events", ["worker_execution_id"])
    op.create_index(op.f("ix_automation_failure_events_failure_type"), "automation_failure_events", ["failure_type"])
    op.create_index(op.f("ix_automation_failure_events_failure_severity"), "automation_failure_events", ["failure_severity"])
    op.create_index(op.f("ix_automation_failure_events_failure_checksum"), "automation_failure_events", ["failure_checksum"])

    op.create_table(
        "automation_recovery_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_run_id"], ["automation_recovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recovery_run_id", "artifact_type", "artifact_checksum", name="uq_automation_recovery_artifact_type_checksum"),
    )
    op.create_index("ix_automation_recovery_artifact_run_created", "automation_recovery_artifacts", ["recovery_run_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_recovery_artifacts_recovery_run_id"), "automation_recovery_artifacts", ["recovery_run_id"])
    op.create_index(op.f("ix_automation_recovery_artifacts_artifact_type"), "automation_recovery_artifacts", ["artifact_type"])
    op.create_index(op.f("ix_automation_recovery_artifacts_storage_backend"), "automation_recovery_artifacts", ["storage_backend"])
    op.create_index(op.f("ix_automation_recovery_artifacts_artifact_checksum"), "automation_recovery_artifacts", ["artifact_checksum"])

    op.create_table(
        "automation_recovery_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_run_id"], ["automation_recovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recovery_run_id", "issue_checksum", name="uq_automation_recovery_issue_checksum"),
    )
    op.create_index("ix_automation_recovery_issue_run_created", "automation_recovery_issues", ["recovery_run_id", "created_at", "id"])
    op.create_index("ix_automation_recovery_issue_type_created", "automation_recovery_issues", ["issue_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_recovery_issues_recovery_run_id"), "automation_recovery_issues", ["recovery_run_id"])
    op.create_index(op.f("ix_automation_recovery_issues_issue_type"), "automation_recovery_issues", ["issue_type"])
    op.create_index(op.f("ix_automation_recovery_issues_severity"), "automation_recovery_issues", ["severity"])
    op.create_index(op.f("ix_automation_recovery_issues_issue_checksum"), "automation_recovery_issues", ["issue_checksum"])

    op.create_table(
        "automation_recovery_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recovery_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recovery_run_id"], ["automation_recovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recovery_run_id", "event_checksum", name="uq_automation_recovery_history_checksum"),
    )
    op.create_index("ix_automation_recovery_history_run_created", "automation_recovery_history", ["recovery_run_id", "created_at", "id"])
    op.create_index("ix_automation_recovery_history_type_created", "automation_recovery_history", ["event_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_recovery_history_recovery_run_id"), "automation_recovery_history", ["recovery_run_id"])
    op.create_index(op.f("ix_automation_recovery_history_event_type"), "automation_recovery_history", ["event_type"])
    op.create_index(op.f("ix_automation_recovery_history_from_status"), "automation_recovery_history", ["from_status"])
    op.create_index(op.f("ix_automation_recovery_history_to_status"), "automation_recovery_history", ["to_status"])
    op.create_index(op.f("ix_automation_recovery_history_event_checksum"), "automation_recovery_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_recovery_history_event_checksum"), table_name="automation_recovery_history")
    op.drop_index(op.f("ix_automation_recovery_history_to_status"), table_name="automation_recovery_history")
    op.drop_index(op.f("ix_automation_recovery_history_from_status"), table_name="automation_recovery_history")
    op.drop_index(op.f("ix_automation_recovery_history_event_type"), table_name="automation_recovery_history")
    op.drop_index(op.f("ix_automation_recovery_history_recovery_run_id"), table_name="automation_recovery_history")
    op.drop_index("ix_automation_recovery_history_type_created", table_name="automation_recovery_history")
    op.drop_index("ix_automation_recovery_history_run_created", table_name="automation_recovery_history")
    op.drop_table("automation_recovery_history")

    op.drop_index(op.f("ix_automation_recovery_issues_issue_checksum"), table_name="automation_recovery_issues")
    op.drop_index(op.f("ix_automation_recovery_issues_severity"), table_name="automation_recovery_issues")
    op.drop_index(op.f("ix_automation_recovery_issues_issue_type"), table_name="automation_recovery_issues")
    op.drop_index(op.f("ix_automation_recovery_issues_recovery_run_id"), table_name="automation_recovery_issues")
    op.drop_index("ix_automation_recovery_issue_type_created", table_name="automation_recovery_issues")
    op.drop_index("ix_automation_recovery_issue_run_created", table_name="automation_recovery_issues")
    op.drop_table("automation_recovery_issues")

    op.drop_index(op.f("ix_automation_recovery_artifacts_artifact_checksum"), table_name="automation_recovery_artifacts")
    op.drop_index(op.f("ix_automation_recovery_artifacts_storage_backend"), table_name="automation_recovery_artifacts")
    op.drop_index(op.f("ix_automation_recovery_artifacts_artifact_type"), table_name="automation_recovery_artifacts")
    op.drop_index(op.f("ix_automation_recovery_artifacts_recovery_run_id"), table_name="automation_recovery_artifacts")
    op.drop_index("ix_automation_recovery_artifact_run_created", table_name="automation_recovery_artifacts")
    op.drop_table("automation_recovery_artifacts")

    op.drop_index(op.f("ix_automation_failure_events_failure_checksum"), table_name="automation_failure_events")
    op.drop_index(op.f("ix_automation_failure_events_failure_severity"), table_name="automation_failure_events")
    op.drop_index(op.f("ix_automation_failure_events_failure_type"), table_name="automation_failure_events")
    op.drop_index(op.f("ix_automation_failure_events_worker_execution_id"), table_name="automation_failure_events")
    op.drop_index(op.f("ix_automation_failure_events_job_id"), table_name="automation_failure_events")
    op.drop_index("ix_automation_failure_event_severity_created", table_name="automation_failure_events")
    op.drop_index("ix_automation_failure_event_job_created", table_name="automation_failure_events")
    op.drop_table("automation_failure_events")

    op.drop_index(op.f("ix_automation_dead_letter_jobs_dead_letter_checksum"), table_name="automation_dead_letter_jobs")
    op.drop_index(op.f("ix_automation_dead_letter_jobs_source_checksum"), table_name="automation_dead_letter_jobs")
    op.drop_index(op.f("ix_automation_dead_letter_jobs_dead_letter_status"), table_name="automation_dead_letter_jobs")
    op.drop_index(op.f("ix_automation_dead_letter_jobs_original_job_id"), table_name="automation_dead_letter_jobs")
    op.drop_index("ix_automation_dead_letter_status_created", table_name="automation_dead_letter_jobs")
    op.drop_table("automation_dead_letter_jobs")

    op.drop_index(op.f("ix_automation_recovery_runs_recovery_checksum"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_recovery_rank"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_recovery_type"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_recovery_status"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_retry_policy_id"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_worker_execution_id"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_job_id"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_organization_id"), table_name="automation_recovery_runs")
    op.drop_index(op.f("ix_automation_recovery_runs_owner_user_id"), table_name="automation_recovery_runs")
    op.drop_index("ix_automation_recovery_run_status_created", table_name="automation_recovery_runs")
    op.drop_index("ix_automation_recovery_run_job_created", table_name="automation_recovery_runs")
    op.drop_table("automation_recovery_runs")

    op.drop_index(op.f("ix_automation_retry_policies_policy_checksum"), table_name="automation_retry_policies")
    op.drop_index(op.f("ix_automation_retry_policies_retry_mode"), table_name="automation_retry_policies")
    op.drop_index(op.f("ix_automation_retry_policies_policy_key"), table_name="automation_retry_policies")
    op.drop_index("ix_automation_retry_policy_mode_created", table_name="automation_retry_policies")
    op.drop_table("automation_retry_policies")
