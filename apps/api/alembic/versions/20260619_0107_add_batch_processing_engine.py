"""add batch processing engine

Revision ID: 20260619_0107
Revises: 20260618_0106
Create Date: 2026-06-19 00:10:07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260619_0107"
down_revision = "20260618_0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_batch_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("batch_key", sa.String(length=120), nullable=False),
        sa.Column("batch_type", sa.String(length=40), nullable=False),
        sa.Column("batch_status", sa.String(length=24), nullable=False),
        sa.Column("source_scope", sa.String(length=80), nullable=False),
        sa.Column("deterministic_partitioning_enabled", sa.Boolean(), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("completed_item_count", sa.Integer(), nullable=False),
        sa.Column("failed_item_count", sa.Integer(), nullable=False),
        sa.Column("batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "batch_key", name="uq_automation_batch_owner_key"),
    )
    op.create_index("ix_automation_batch_run_status_created", "automation_batch_runs", ["batch_status", "created_at", "id"])
    op.create_index("ix_automation_batch_run_type_created", "automation_batch_runs", ["batch_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_batch_runs_owner_user_id"), "automation_batch_runs", ["owner_user_id"])
    op.create_index(op.f("ix_automation_batch_runs_organization_id"), "automation_batch_runs", ["organization_id"])
    op.create_index(op.f("ix_automation_batch_runs_batch_key"), "automation_batch_runs", ["batch_key"])
    op.create_index(op.f("ix_automation_batch_runs_batch_type"), "automation_batch_runs", ["batch_type"])
    op.create_index(op.f("ix_automation_batch_runs_batch_status"), "automation_batch_runs", ["batch_status"])
    op.create_index(op.f("ix_automation_batch_runs_source_scope"), "automation_batch_runs", ["source_scope"])
    op.create_index(op.f("ix_automation_batch_runs_batch_checksum"), "automation_batch_runs", ["batch_checksum"])

    op.create_table(
        "automation_batch_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_run_id", sa.Integer(), nullable=False),
        sa.Column("chunk_rank", sa.Integer(), nullable=False),
        sa.Column("chunk_status", sa.String(length=24), nullable=False),
        sa.Column("partition_key", sa.String(length=120), nullable=False),
        sa.Column("item_start", sa.Integer(), nullable=False),
        sa.Column("item_end", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("chunk_checksum", sa.String(length=64), nullable=False),
        sa.Column("worker_execution_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["automation_batch_runs.id"]),
        sa.ForeignKeyConstraint(["worker_execution_id"], ["automation_worker_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_run_id", "chunk_rank", name="uq_automation_batch_chunk_rank"),
    )
    op.create_index("ix_automation_batch_chunk_run_created", "automation_batch_chunks", ["batch_run_id", "created_at", "id"])
    op.create_index("ix_automation_batch_chunk_status_created", "automation_batch_chunks", ["chunk_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_batch_chunks_batch_run_id"), "automation_batch_chunks", ["batch_run_id"])
    op.create_index(op.f("ix_automation_batch_chunks_chunk_rank"), "automation_batch_chunks", ["chunk_rank"])
    op.create_index(op.f("ix_automation_batch_chunks_chunk_status"), "automation_batch_chunks", ["chunk_status"])
    op.create_index(op.f("ix_automation_batch_chunks_partition_key"), "automation_batch_chunks", ["partition_key"])
    op.create_index(op.f("ix_automation_batch_chunks_chunk_checksum"), "automation_batch_chunks", ["chunk_checksum"])
    op.create_index(op.f("ix_automation_batch_chunks_worker_execution_id"), "automation_batch_chunks", ["worker_execution_id"])

    op.create_table(
        "automation_maintenance_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_key", sa.String(length=120), nullable=False),
        sa.Column("maintenance_type", sa.String(length=40), nullable=False),
        sa.Column("maintenance_status", sa.String(length=24), nullable=False),
        sa.Column("maintenance_scope", sa.String(length=80), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("maintenance_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "maintenance_key", name="uq_automation_maintenance_owner_key"),
    )
    op.create_index("ix_automation_maintenance_job_status_created", "automation_maintenance_jobs", ["maintenance_status", "created_at", "id"])
    op.create_index("ix_automation_maintenance_job_type_created", "automation_maintenance_jobs", ["maintenance_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_maintenance_jobs_owner_user_id"), "automation_maintenance_jobs", ["owner_user_id"])
    op.create_index(op.f("ix_automation_maintenance_jobs_organization_id"), "automation_maintenance_jobs", ["organization_id"])
    op.create_index(op.f("ix_automation_maintenance_jobs_maintenance_key"), "automation_maintenance_jobs", ["maintenance_key"])
    op.create_index(op.f("ix_automation_maintenance_jobs_maintenance_type"), "automation_maintenance_jobs", ["maintenance_type"])
    op.create_index(op.f("ix_automation_maintenance_jobs_maintenance_status"), "automation_maintenance_jobs", ["maintenance_status"])
    op.create_index(op.f("ix_automation_maintenance_jobs_maintenance_scope"), "automation_maintenance_jobs", ["maintenance_scope"])
    op.create_index(op.f("ix_automation_maintenance_jobs_maintenance_checksum"), "automation_maintenance_jobs", ["maintenance_checksum"])

    op.create_table(
        "automation_maintenance_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("maintenance_job_id", sa.Integer(), nullable=False),
        sa.Column("result_type", sa.String(length=32), nullable=False),
        sa.Column("result_status", sa.String(length=16), nullable=False),
        sa.Column("result_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("result_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["maintenance_job_id"], ["automation_maintenance_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("maintenance_job_id", "result_checksum", name="uq_automation_maintenance_result_checksum"),
    )
    op.create_index("ix_automation_maintenance_result_job_created", "automation_maintenance_results", ["maintenance_job_id", "created_at", "id"])
    op.create_index("ix_automation_maintenance_result_status_created", "automation_maintenance_results", ["result_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_maintenance_results_maintenance_job_id"), "automation_maintenance_results", ["maintenance_job_id"])
    op.create_index(op.f("ix_automation_maintenance_results_result_type"), "automation_maintenance_results", ["result_type"])
    op.create_index(op.f("ix_automation_maintenance_results_result_status"), "automation_maintenance_results", ["result_status"])
    op.create_index(op.f("ix_automation_maintenance_results_result_checksum"), "automation_maintenance_results", ["result_checksum"])

    op.create_table(
        "automation_batch_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_run_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_job_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["automation_batch_runs.id"]),
        sa.ForeignKeyConstraint(["maintenance_job_id"], ["automation_maintenance_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_run_id", "maintenance_job_id", "artifact_type", "artifact_checksum", name="uq_automation_batch_artifact_type_checksum"),
    )
    op.create_index("ix_automation_batch_artifact_batch_created", "automation_batch_artifacts", ["batch_run_id", "created_at", "id"])
    op.create_index("ix_automation_batch_artifact_maintenance_created", "automation_batch_artifacts", ["maintenance_job_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_batch_artifacts_batch_run_id"), "automation_batch_artifacts", ["batch_run_id"])
    op.create_index(op.f("ix_automation_batch_artifacts_maintenance_job_id"), "automation_batch_artifacts", ["maintenance_job_id"])
    op.create_index(op.f("ix_automation_batch_artifacts_artifact_type"), "automation_batch_artifacts", ["artifact_type"])
    op.create_index(op.f("ix_automation_batch_artifacts_storage_backend"), "automation_batch_artifacts", ["storage_backend"])
    op.create_index(op.f("ix_automation_batch_artifacts_artifact_checksum"), "automation_batch_artifacts", ["artifact_checksum"])

    op.create_table(
        "automation_batch_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_run_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_job_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["automation_batch_runs.id"]),
        sa.ForeignKeyConstraint(["maintenance_job_id"], ["automation_maintenance_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_run_id", "maintenance_job_id", "issue_checksum", name="uq_automation_batch_issue_checksum"),
    )
    op.create_index("ix_automation_batch_issue_batch_created", "automation_batch_issues", ["batch_run_id", "created_at", "id"])
    op.create_index("ix_automation_batch_issue_maintenance_created", "automation_batch_issues", ["maintenance_job_id", "created_at", "id"])
    op.create_index("ix_automation_batch_issue_type_created", "automation_batch_issues", ["issue_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_batch_issues_batch_run_id"), "automation_batch_issues", ["batch_run_id"])
    op.create_index(op.f("ix_automation_batch_issues_maintenance_job_id"), "automation_batch_issues", ["maintenance_job_id"])
    op.create_index(op.f("ix_automation_batch_issues_issue_type"), "automation_batch_issues", ["issue_type"])
    op.create_index(op.f("ix_automation_batch_issues_severity"), "automation_batch_issues", ["severity"])
    op.create_index(op.f("ix_automation_batch_issues_issue_checksum"), "automation_batch_issues", ["issue_checksum"])

    op.create_table(
        "automation_batch_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_run_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_job_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["automation_batch_runs.id"]),
        sa.ForeignKeyConstraint(["maintenance_job_id"], ["automation_maintenance_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_run_id", "maintenance_job_id", "event_checksum", name="uq_automation_batch_history_checksum"),
    )
    op.create_index("ix_automation_batch_history_batch_created", "automation_batch_history", ["batch_run_id", "created_at", "id"])
    op.create_index("ix_automation_batch_history_maintenance_created", "automation_batch_history", ["maintenance_job_id", "created_at", "id"])
    op.create_index("ix_automation_batch_history_type_created", "automation_batch_history", ["event_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_batch_history_batch_run_id"), "automation_batch_history", ["batch_run_id"])
    op.create_index(op.f("ix_automation_batch_history_maintenance_job_id"), "automation_batch_history", ["maintenance_job_id"])
    op.create_index(op.f("ix_automation_batch_history_event_type"), "automation_batch_history", ["event_type"])
    op.create_index(op.f("ix_automation_batch_history_from_status"), "automation_batch_history", ["from_status"])
    op.create_index(op.f("ix_automation_batch_history_to_status"), "automation_batch_history", ["to_status"])
    op.create_index(op.f("ix_automation_batch_history_event_checksum"), "automation_batch_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_batch_history_event_checksum"), table_name="automation_batch_history")
    op.drop_index(op.f("ix_automation_batch_history_to_status"), table_name="automation_batch_history")
    op.drop_index(op.f("ix_automation_batch_history_from_status"), table_name="automation_batch_history")
    op.drop_index(op.f("ix_automation_batch_history_event_type"), table_name="automation_batch_history")
    op.drop_index(op.f("ix_automation_batch_history_maintenance_job_id"), table_name="automation_batch_history")
    op.drop_index(op.f("ix_automation_batch_history_batch_run_id"), table_name="automation_batch_history")
    op.drop_index("ix_automation_batch_history_type_created", table_name="automation_batch_history")
    op.drop_index("ix_automation_batch_history_maintenance_created", table_name="automation_batch_history")
    op.drop_index("ix_automation_batch_history_batch_created", table_name="automation_batch_history")
    op.drop_table("automation_batch_history")

    op.drop_index(op.f("ix_automation_batch_issues_issue_checksum"), table_name="automation_batch_issues")
    op.drop_index(op.f("ix_automation_batch_issues_severity"), table_name="automation_batch_issues")
    op.drop_index(op.f("ix_automation_batch_issues_issue_type"), table_name="automation_batch_issues")
    op.drop_index(op.f("ix_automation_batch_issues_maintenance_job_id"), table_name="automation_batch_issues")
    op.drop_index(op.f("ix_automation_batch_issues_batch_run_id"), table_name="automation_batch_issues")
    op.drop_index("ix_automation_batch_issue_type_created", table_name="automation_batch_issues")
    op.drop_index("ix_automation_batch_issue_maintenance_created", table_name="automation_batch_issues")
    op.drop_index("ix_automation_batch_issue_batch_created", table_name="automation_batch_issues")
    op.drop_table("automation_batch_issues")

    op.drop_index(op.f("ix_automation_batch_artifacts_artifact_checksum"), table_name="automation_batch_artifacts")
    op.drop_index(op.f("ix_automation_batch_artifacts_storage_backend"), table_name="automation_batch_artifacts")
    op.drop_index(op.f("ix_automation_batch_artifacts_artifact_type"), table_name="automation_batch_artifacts")
    op.drop_index(op.f("ix_automation_batch_artifacts_maintenance_job_id"), table_name="automation_batch_artifacts")
    op.drop_index(op.f("ix_automation_batch_artifacts_batch_run_id"), table_name="automation_batch_artifacts")
    op.drop_index("ix_automation_batch_artifact_maintenance_created", table_name="automation_batch_artifacts")
    op.drop_index("ix_automation_batch_artifact_batch_created", table_name="automation_batch_artifacts")
    op.drop_table("automation_batch_artifacts")

    op.drop_index(op.f("ix_automation_maintenance_results_result_checksum"), table_name="automation_maintenance_results")
    op.drop_index(op.f("ix_automation_maintenance_results_result_status"), table_name="automation_maintenance_results")
    op.drop_index(op.f("ix_automation_maintenance_results_result_type"), table_name="automation_maintenance_results")
    op.drop_index(op.f("ix_automation_maintenance_results_maintenance_job_id"), table_name="automation_maintenance_results")
    op.drop_index("ix_automation_maintenance_result_status_created", table_name="automation_maintenance_results")
    op.drop_index("ix_automation_maintenance_result_job_created", table_name="automation_maintenance_results")
    op.drop_table("automation_maintenance_results")

    op.drop_index(op.f("ix_automation_maintenance_jobs_maintenance_checksum"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_maintenance_scope"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_maintenance_status"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_maintenance_type"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_maintenance_key"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_organization_id"), table_name="automation_maintenance_jobs")
    op.drop_index(op.f("ix_automation_maintenance_jobs_owner_user_id"), table_name="automation_maintenance_jobs")
    op.drop_index("ix_automation_maintenance_job_type_created", table_name="automation_maintenance_jobs")
    op.drop_index("ix_automation_maintenance_job_status_created", table_name="automation_maintenance_jobs")
    op.drop_table("automation_maintenance_jobs")

    op.drop_index(op.f("ix_automation_batch_chunks_worker_execution_id"), table_name="automation_batch_chunks")
    op.drop_index(op.f("ix_automation_batch_chunks_chunk_checksum"), table_name="automation_batch_chunks")
    op.drop_index(op.f("ix_automation_batch_chunks_partition_key"), table_name="automation_batch_chunks")
    op.drop_index(op.f("ix_automation_batch_chunks_chunk_status"), table_name="automation_batch_chunks")
    op.drop_index(op.f("ix_automation_batch_chunks_chunk_rank"), table_name="automation_batch_chunks")
    op.drop_index(op.f("ix_automation_batch_chunks_batch_run_id"), table_name="automation_batch_chunks")
    op.drop_index("ix_automation_batch_chunk_status_created", table_name="automation_batch_chunks")
    op.drop_index("ix_automation_batch_chunk_run_created", table_name="automation_batch_chunks")
    op.drop_table("automation_batch_chunks")

    op.drop_index(op.f("ix_automation_batch_runs_batch_checksum"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_source_scope"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_batch_status"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_batch_type"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_batch_key"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_organization_id"), table_name="automation_batch_runs")
    op.drop_index(op.f("ix_automation_batch_runs_owner_user_id"), table_name="automation_batch_runs")
    op.drop_index("ix_automation_batch_run_type_created", table_name="automation_batch_runs")
    op.drop_index("ix_automation_batch_run_status_created", table_name="automation_batch_runs")
    op.drop_table("automation_batch_runs")
