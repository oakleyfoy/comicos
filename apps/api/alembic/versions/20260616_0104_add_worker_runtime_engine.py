"""add worker runtime engine

Revision ID: 20260616_0104
Revises: 20260615_0103
Create Date: 2026-06-16 00:10:04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260616_0104"
down_revision = "20260615_0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_workers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_key", sa.String(length=80), nullable=False),
        sa.Column("worker_identifier", sa.String(length=160), nullable=False),
        sa.Column("worker_type", sa.String(length=32), nullable=False),
        sa.Column("worker_status", sa.String(length=24), nullable=False),
        sa.Column("process_identifier", sa.String(length=80), nullable=True),
        sa.Column("hostname", sa.String(length=160), nullable=True),
        sa.Column("queue_scope_json", sa.JSON(), nullable=False),
        sa.Column("current_job_id", sa.Integer(), nullable=True),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("startup_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shutdown_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["current_job_id"], ["automation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_identifier", name="uq_automation_worker_identifier"),
        sa.UniqueConstraint("worker_key", name="uq_automation_worker_key"),
    )
    op.create_index("ix_automation_worker_status_created", "automation_workers", ["worker_status", "created_at", "id"])
    op.create_index("ix_automation_worker_type_created", "automation_workers", ["worker_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_workers_worker_key"), "automation_workers", ["worker_key"])
    op.create_index(op.f("ix_automation_workers_worker_identifier"), "automation_workers", ["worker_identifier"])
    op.create_index(op.f("ix_automation_workers_worker_type"), "automation_workers", ["worker_type"])
    op.create_index(op.f("ix_automation_workers_worker_status"), "automation_workers", ["worker_status"])
    op.create_index(op.f("ix_automation_workers_hostname"), "automation_workers", ["hostname"])
    op.create_index(op.f("ix_automation_workers_current_job_id"), "automation_workers", ["current_job_id"])

    op.create_table(
        "automation_worker_heartbeats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("heartbeat_status", sa.String(length=16), nullable=False),
        sa.Column("active_job_count", sa.Integer(), nullable=False),
        sa.Column("memory_usage_mb", sa.Integer(), nullable=True),
        sa.Column("cpu_usage_percent", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["automation_workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_worker_heartbeat_worker_created", "automation_worker_heartbeats", ["worker_id", "created_at", "id"])
    op.create_index("ix_automation_worker_heartbeat_status_created", "automation_worker_heartbeats", ["heartbeat_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_worker_heartbeats_worker_id"), "automation_worker_heartbeats", ["worker_id"])
    op.create_index(op.f("ix_automation_worker_heartbeats_heartbeat_status"), "automation_worker_heartbeats", ["heartbeat_status"])

    op.create_table(
        "automation_worker_leases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("reservation_token", sa.String(length=128), nullable=False),
        sa.Column("lease_status", sa.String(length=16), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["automation_workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_token", name="uq_automation_worker_lease_token"),
    )
    op.create_index("ix_automation_worker_lease_worker_created", "automation_worker_leases", ["worker_id", "created_at", "id"])
    op.create_index("ix_automation_worker_lease_job_created", "automation_worker_leases", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_worker_lease_status_expires", "automation_worker_leases", ["lease_status", "lease_expires_at", "id"])
    op.create_index(op.f("ix_automation_worker_leases_worker_id"), "automation_worker_leases", ["worker_id"])
    op.create_index(op.f("ix_automation_worker_leases_job_id"), "automation_worker_leases", ["job_id"])
    op.create_index(op.f("ix_automation_worker_leases_reservation_token"), "automation_worker_leases", ["reservation_token"])
    op.create_index(op.f("ix_automation_worker_leases_lease_status"), "automation_worker_leases", ["lease_status"])

    op.create_table(
        "automation_worker_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("execution_status", sa.String(length=16), nullable=False),
        sa.Column("execution_rank", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("execution_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("execution_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["automation_workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_checksum", name="uq_automation_worker_exec_checksum"),
        sa.UniqueConstraint("worker_id", "job_id", "execution_rank", name="uq_automation_worker_exec_worker_job_rank"),
    )
    op.create_index("ix_automation_worker_exec_worker_created", "automation_worker_executions", ["worker_id", "created_at", "id"])
    op.create_index("ix_automation_worker_exec_job_created", "automation_worker_executions", ["job_id", "created_at", "id"])
    op.create_index("ix_automation_worker_exec_status_created", "automation_worker_executions", ["execution_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_worker_executions_worker_id"), "automation_worker_executions", ["worker_id"])
    op.create_index(op.f("ix_automation_worker_executions_job_id"), "automation_worker_executions", ["job_id"])
    op.create_index(op.f("ix_automation_worker_executions_execution_status"), "automation_worker_executions", ["execution_status"])
    op.create_index(op.f("ix_automation_worker_executions_execution_rank"), "automation_worker_executions", ["execution_rank"])
    op.create_index(op.f("ix_automation_worker_executions_execution_checksum"), "automation_worker_executions", ["execution_checksum"])

    op.create_table(
        "automation_worker_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["automation_workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id", "issue_checksum", name="uq_automation_worker_issue_checksum"),
    )
    op.create_index("ix_automation_worker_issue_worker_created", "automation_worker_issues", ["worker_id", "created_at", "id"])
    op.create_index("ix_automation_worker_issue_type_created", "automation_worker_issues", ["issue_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_worker_issues_worker_id"), "automation_worker_issues", ["worker_id"])
    op.create_index(op.f("ix_automation_worker_issues_job_id"), "automation_worker_issues", ["job_id"])
    op.create_index(op.f("ix_automation_worker_issues_issue_type"), "automation_worker_issues", ["issue_type"])
    op.create_index(op.f("ix_automation_worker_issues_severity"), "automation_worker_issues", ["severity"])
    op.create_index(op.f("ix_automation_worker_issues_issue_checksum"), "automation_worker_issues", ["issue_checksum"])

    op.create_table(
        "automation_worker_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["automation_workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id", "event_checksum", name="uq_automation_worker_history_checksum"),
    )
    op.create_index("ix_automation_worker_history_worker_created", "automation_worker_history", ["worker_id", "created_at", "id"])
    op.create_index("ix_automation_worker_history_type_created", "automation_worker_history", ["event_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_worker_history_worker_id"), "automation_worker_history", ["worker_id"])
    op.create_index(op.f("ix_automation_worker_history_job_id"), "automation_worker_history", ["job_id"])
    op.create_index(op.f("ix_automation_worker_history_event_type"), "automation_worker_history", ["event_type"])
    op.create_index(op.f("ix_automation_worker_history_from_status"), "automation_worker_history", ["from_status"])
    op.create_index(op.f("ix_automation_worker_history_to_status"), "automation_worker_history", ["to_status"])
    op.create_index(op.f("ix_automation_worker_history_event_checksum"), "automation_worker_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_worker_history_event_checksum"), table_name="automation_worker_history")
    op.drop_index(op.f("ix_automation_worker_history_to_status"), table_name="automation_worker_history")
    op.drop_index(op.f("ix_automation_worker_history_from_status"), table_name="automation_worker_history")
    op.drop_index(op.f("ix_automation_worker_history_event_type"), table_name="automation_worker_history")
    op.drop_index(op.f("ix_automation_worker_history_job_id"), table_name="automation_worker_history")
    op.drop_index(op.f("ix_automation_worker_history_worker_id"), table_name="automation_worker_history")
    op.drop_index("ix_automation_worker_history_type_created", table_name="automation_worker_history")
    op.drop_index("ix_automation_worker_history_worker_created", table_name="automation_worker_history")
    op.drop_table("automation_worker_history")

    op.drop_index(op.f("ix_automation_worker_issues_issue_checksum"), table_name="automation_worker_issues")
    op.drop_index(op.f("ix_automation_worker_issues_severity"), table_name="automation_worker_issues")
    op.drop_index(op.f("ix_automation_worker_issues_issue_type"), table_name="automation_worker_issues")
    op.drop_index(op.f("ix_automation_worker_issues_job_id"), table_name="automation_worker_issues")
    op.drop_index(op.f("ix_automation_worker_issues_worker_id"), table_name="automation_worker_issues")
    op.drop_index("ix_automation_worker_issue_type_created", table_name="automation_worker_issues")
    op.drop_index("ix_automation_worker_issue_worker_created", table_name="automation_worker_issues")
    op.drop_table("automation_worker_issues")

    op.drop_index(op.f("ix_automation_worker_executions_execution_checksum"), table_name="automation_worker_executions")
    op.drop_index(op.f("ix_automation_worker_executions_execution_rank"), table_name="automation_worker_executions")
    op.drop_index(op.f("ix_automation_worker_executions_execution_status"), table_name="automation_worker_executions")
    op.drop_index(op.f("ix_automation_worker_executions_job_id"), table_name="automation_worker_executions")
    op.drop_index(op.f("ix_automation_worker_executions_worker_id"), table_name="automation_worker_executions")
    op.drop_index("ix_automation_worker_exec_status_created", table_name="automation_worker_executions")
    op.drop_index("ix_automation_worker_exec_job_created", table_name="automation_worker_executions")
    op.drop_index("ix_automation_worker_exec_worker_created", table_name="automation_worker_executions")
    op.drop_table("automation_worker_executions")

    op.drop_index(op.f("ix_automation_worker_leases_lease_status"), table_name="automation_worker_leases")
    op.drop_index(op.f("ix_automation_worker_leases_reservation_token"), table_name="automation_worker_leases")
    op.drop_index(op.f("ix_automation_worker_leases_job_id"), table_name="automation_worker_leases")
    op.drop_index(op.f("ix_automation_worker_leases_worker_id"), table_name="automation_worker_leases")
    op.drop_index("ix_automation_worker_lease_status_expires", table_name="automation_worker_leases")
    op.drop_index("ix_automation_worker_lease_job_created", table_name="automation_worker_leases")
    op.drop_index("ix_automation_worker_lease_worker_created", table_name="automation_worker_leases")
    op.drop_table("automation_worker_leases")

    op.drop_index(op.f("ix_automation_worker_heartbeats_heartbeat_status"), table_name="automation_worker_heartbeats")
    op.drop_index(op.f("ix_automation_worker_heartbeats_worker_id"), table_name="automation_worker_heartbeats")
    op.drop_index("ix_automation_worker_heartbeat_status_created", table_name="automation_worker_heartbeats")
    op.drop_index("ix_automation_worker_heartbeat_worker_created", table_name="automation_worker_heartbeats")
    op.drop_table("automation_worker_heartbeats")

    op.drop_index(op.f("ix_automation_workers_current_job_id"), table_name="automation_workers")
    op.drop_index(op.f("ix_automation_workers_hostname"), table_name="automation_workers")
    op.drop_index(op.f("ix_automation_workers_worker_status"), table_name="automation_workers")
    op.drop_index(op.f("ix_automation_workers_worker_type"), table_name="automation_workers")
    op.drop_index(op.f("ix_automation_workers_worker_identifier"), table_name="automation_workers")
    op.drop_index(op.f("ix_automation_workers_worker_key"), table_name="automation_workers")
    op.drop_index("ix_automation_worker_type_created", table_name="automation_workers")
    op.drop_index("ix_automation_worker_status_created", table_name="automation_workers")
    op.drop_table("automation_workers")
