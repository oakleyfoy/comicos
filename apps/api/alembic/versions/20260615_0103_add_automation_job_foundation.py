"""add automation job foundation

Revision ID: 20260615_0103
Revises: 20260614_0102
Create Date: 2026-06-15 00:10:03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260615_0103"
down_revision = "20260614_0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_queues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("queue_key", sa.String(length=80), nullable=False),
        sa.Column("queue_name", sa.String(length=160), nullable=False),
        sa.Column("queue_category", sa.String(length=32), nullable=False),
        sa.Column("queue_status", sa.String(length=24), nullable=False),
        sa.Column("deterministic_ordering_enabled", sa.Boolean(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("queue_key", name="uq_automation_queue_key"),
    )
    op.create_index("ix_automation_queue_status_created", "automation_queues", ["queue_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_queues_queue_key"), "automation_queues", ["queue_key"])
    op.create_index(op.f("ix_automation_queues_queue_category"), "automation_queues", ["queue_category"])
    op.create_index(op.f("ix_automation_queues_queue_status"), "automation_queues", ["queue_status"])

    op.create_table(
        "automation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("queue_id", sa.Integer(), nullable=False),
        sa.Column("parent_job_id", sa.Integer(), nullable=True),
        sa.Column("job_key", sa.String(length=160), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("job_status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("deterministic_rank", sa.Integer(), nullable=False),
        sa.Column("payload_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("source_record_type", sa.String(length=80), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("reservation_token", sa.String(length=128), nullable=True),
        sa.Column("reserved_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("current_attempt_count", sa.Integer(), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("job_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["parent_job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["queue_id"], ["automation_queues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("queue_id", "job_key", name="uq_automation_job_queue_key"),
    )
    op.create_index("ix_automation_job_owner_created", "automation_jobs", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_automation_job_org_created", "automation_jobs", ["organization_id", "created_at", "id"])
    op.create_index("ix_automation_job_queue_status_rank", "automation_jobs", ["queue_id", "job_status", "deterministic_rank", "id"])
    op.create_index("ix_automation_job_queue_available", "automation_jobs", ["queue_id", "available_at", "id"])
    op.create_index(op.f("ix_automation_jobs_owner_user_id"), "automation_jobs", ["owner_user_id"])
    op.create_index(op.f("ix_automation_jobs_organization_id"), "automation_jobs", ["organization_id"])
    op.create_index(op.f("ix_automation_jobs_queue_id"), "automation_jobs", ["queue_id"])
    op.create_index(op.f("ix_automation_jobs_parent_job_id"), "automation_jobs", ["parent_job_id"])
    op.create_index(op.f("ix_automation_jobs_job_key"), "automation_jobs", ["job_key"])
    op.create_index(op.f("ix_automation_jobs_job_type"), "automation_jobs", ["job_type"])
    op.create_index(op.f("ix_automation_jobs_job_status"), "automation_jobs", ["job_status"])
    op.create_index(op.f("ix_automation_jobs_priority"), "automation_jobs", ["priority"])
    op.create_index(op.f("ix_automation_jobs_deterministic_rank"), "automation_jobs", ["deterministic_rank"])
    op.create_index(op.f("ix_automation_jobs_payload_checksum"), "automation_jobs", ["payload_checksum"])
    op.create_index(op.f("ix_automation_jobs_source_record_type"), "automation_jobs", ["source_record_type"])
    op.create_index(op.f("ix_automation_jobs_source_record_id"), "automation_jobs", ["source_record_id"])
    op.create_index(op.f("ix_automation_jobs_source_checksum"), "automation_jobs", ["source_checksum"])
    op.create_index(op.f("ix_automation_jobs_reservation_token"), "automation_jobs", ["reservation_token"])
    op.create_index(op.f("ix_automation_jobs_available_at"), "automation_jobs", ["available_at"])
    op.create_index(op.f("ix_automation_jobs_idempotency_key"), "automation_jobs", ["idempotency_key"])
    op.create_index(op.f("ix_automation_jobs_job_checksum"), "automation_jobs", ["job_checksum"])

    op.create_table(
        "automation_job_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("attempt_status", sa.String(length=16), nullable=False),
        sa.Column("worker_identifier", sa.String(length=160), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=1024), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_automation_job_attempt_job_number"),
    )
    op.create_index("ix_automation_job_attempt_job_created", "automation_job_attempts", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_job_attempt_status_created", "automation_job_attempts", ["attempt_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_job_attempts_job_id"), "automation_job_attempts", ["job_id"])
    op.create_index(op.f("ix_automation_job_attempts_attempt_status"), "automation_job_attempts", ["attempt_status"])
    op.create_index(op.f("ix_automation_job_attempts_worker_identifier"), "automation_job_attempts", ["worker_identifier"])

    op.create_table(
        "automation_job_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("depends_on_job_id", sa.Integer(), nullable=False),
        sa.Column("dependency_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["depends_on_job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "depends_on_job_id", name="uq_automation_job_dependency_edge"),
    )
    op.create_index("ix_automation_job_dependency_job_created", "automation_job_dependencies", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_job_dependency_dep_created", "automation_job_dependencies", ["depends_on_job_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_job_dependencies_job_id"), "automation_job_dependencies", ["job_id"])
    op.create_index(op.f("ix_automation_job_dependencies_depends_on_job_id"), "automation_job_dependencies", ["depends_on_job_id"])
    op.create_index(op.f("ix_automation_job_dependencies_dependency_status"), "automation_job_dependencies", ["dependency_status"])

    op.create_table(
        "automation_job_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "artifact_type", "artifact_checksum", name="uq_automation_job_artifact_type_checksum"),
    )
    op.create_index("ix_automation_job_artifact_job_created", "automation_job_artifacts", ["job_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_job_artifacts_job_id"), "automation_job_artifacts", ["job_id"])
    op.create_index(op.f("ix_automation_job_artifacts_artifact_type"), "automation_job_artifacts", ["artifact_type"])
    op.create_index(op.f("ix_automation_job_artifacts_storage_backend"), "automation_job_artifacts", ["storage_backend"])
    op.create_index(op.f("ix_automation_job_artifacts_artifact_checksum"), "automation_job_artifacts", ["artifact_checksum"])

    op.create_table(
        "automation_job_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "issue_checksum", name="uq_automation_job_issue_checksum"),
    )
    op.create_index("ix_automation_job_issue_job_created", "automation_job_issues", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_job_issue_type_created", "automation_job_issues", ["issue_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_job_issues_job_id"), "automation_job_issues", ["job_id"])
    op.create_index(op.f("ix_automation_job_issues_issue_type"), "automation_job_issues", ["issue_type"])
    op.create_index(op.f("ix_automation_job_issues_severity"), "automation_job_issues", ["severity"])
    op.create_index(op.f("ix_automation_job_issues_issue_checksum"), "automation_job_issues", ["issue_checksum"])

    op.create_table(
        "automation_job_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "event_checksum", name="uq_automation_job_history_checksum"),
    )
    op.create_index("ix_automation_job_history_job_created", "automation_job_history", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_job_history_type_created", "automation_job_history", ["event_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_job_history_job_id"), "automation_job_history", ["job_id"])
    op.create_index(op.f("ix_automation_job_history_event_type"), "automation_job_history", ["event_type"])
    op.create_index(op.f("ix_automation_job_history_from_status"), "automation_job_history", ["from_status"])
    op.create_index(op.f("ix_automation_job_history_to_status"), "automation_job_history", ["to_status"])
    op.create_index(op.f("ix_automation_job_history_event_checksum"), "automation_job_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_job_history_event_checksum"), table_name="automation_job_history")
    op.drop_index(op.f("ix_automation_job_history_to_status"), table_name="automation_job_history")
    op.drop_index(op.f("ix_automation_job_history_from_status"), table_name="automation_job_history")
    op.drop_index(op.f("ix_automation_job_history_event_type"), table_name="automation_job_history")
    op.drop_index(op.f("ix_automation_job_history_job_id"), table_name="automation_job_history")
    op.drop_index("ix_automation_job_history_type_created", table_name="automation_job_history")
    op.drop_index("ix_automation_job_history_job_created", table_name="automation_job_history")
    op.drop_table("automation_job_history")

    op.drop_index(op.f("ix_automation_job_issues_issue_checksum"), table_name="automation_job_issues")
    op.drop_index(op.f("ix_automation_job_issues_severity"), table_name="automation_job_issues")
    op.drop_index(op.f("ix_automation_job_issues_issue_type"), table_name="automation_job_issues")
    op.drop_index(op.f("ix_automation_job_issues_job_id"), table_name="automation_job_issues")
    op.drop_index("ix_automation_job_issue_type_created", table_name="automation_job_issues")
    op.drop_index("ix_automation_job_issue_job_created", table_name="automation_job_issues")
    op.drop_table("automation_job_issues")

    op.drop_index(op.f("ix_automation_job_artifacts_artifact_checksum"), table_name="automation_job_artifacts")
    op.drop_index(op.f("ix_automation_job_artifacts_storage_backend"), table_name="automation_job_artifacts")
    op.drop_index(op.f("ix_automation_job_artifacts_artifact_type"), table_name="automation_job_artifacts")
    op.drop_index(op.f("ix_automation_job_artifacts_job_id"), table_name="automation_job_artifacts")
    op.drop_index("ix_automation_job_artifact_job_created", table_name="automation_job_artifacts")
    op.drop_table("automation_job_artifacts")

    op.drop_index(op.f("ix_automation_job_dependencies_dependency_status"), table_name="automation_job_dependencies")
    op.drop_index(op.f("ix_automation_job_dependencies_depends_on_job_id"), table_name="automation_job_dependencies")
    op.drop_index(op.f("ix_automation_job_dependencies_job_id"), table_name="automation_job_dependencies")
    op.drop_index("ix_automation_job_dependency_dep_created", table_name="automation_job_dependencies")
    op.drop_index("ix_automation_job_dependency_job_created", table_name="automation_job_dependencies")
    op.drop_table("automation_job_dependencies")

    op.drop_index(op.f("ix_automation_job_attempts_worker_identifier"), table_name="automation_job_attempts")
    op.drop_index(op.f("ix_automation_job_attempts_attempt_status"), table_name="automation_job_attempts")
    op.drop_index(op.f("ix_automation_job_attempts_job_id"), table_name="automation_job_attempts")
    op.drop_index("ix_automation_job_attempt_status_created", table_name="automation_job_attempts")
    op.drop_index("ix_automation_job_attempt_job_created", table_name="automation_job_attempts")
    op.drop_table("automation_job_attempts")

    op.drop_index(op.f("ix_automation_jobs_job_checksum"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_idempotency_key"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_available_at"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_reservation_token"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_source_checksum"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_source_record_id"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_source_record_type"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_payload_checksum"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_deterministic_rank"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_priority"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_job_status"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_job_type"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_job_key"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_parent_job_id"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_queue_id"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_organization_id"), table_name="automation_jobs")
    op.drop_index(op.f("ix_automation_jobs_owner_user_id"), table_name="automation_jobs")
    op.drop_index("ix_automation_job_queue_available", table_name="automation_jobs")
    op.drop_index("ix_automation_job_queue_status_rank", table_name="automation_jobs")
    op.drop_index("ix_automation_job_org_created", table_name="automation_jobs")
    op.drop_index("ix_automation_job_owner_created", table_name="automation_jobs")
    op.drop_table("automation_jobs")

    op.drop_index(op.f("ix_automation_queues_queue_status"), table_name="automation_queues")
    op.drop_index(op.f("ix_automation_queues_queue_category"), table_name="automation_queues")
    op.drop_index(op.f("ix_automation_queues_queue_key"), table_name="automation_queues")
    op.drop_index("ix_automation_queue_status_created", table_name="automation_queues")
    op.drop_table("automation_queues")
