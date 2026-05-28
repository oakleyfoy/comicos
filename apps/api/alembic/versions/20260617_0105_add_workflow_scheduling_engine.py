"""add workflow scheduling engine

Revision ID: 20260617_0105
Revises: 20260616_0104
Create Date: 2026-06-17 00:10:05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260617_0105"
down_revision = "20260616_0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("schedule_key", sa.String(length=120), nullable=False),
        sa.Column("schedule_name", sa.String(length=160), nullable=False),
        sa.Column("schedule_type", sa.String(length=24), nullable=False),
        sa.Column("schedule_status", sa.String(length=24), nullable=False),
        sa.Column("cron_expression", sa.String(length=120), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("deterministic_ordering_enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "schedule_key", name="uq_automation_schedule_owner_key"),
    )
    op.create_index("ix_automation_schedule_status_next", "automation_schedules", ["schedule_status", "next_run_at", "id"])
    op.create_index("ix_automation_schedule_owner_created", "automation_schedules", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_schedules_owner_user_id"), "automation_schedules", ["owner_user_id"])
    op.create_index(op.f("ix_automation_schedules_organization_id"), "automation_schedules", ["organization_id"])
    op.create_index(op.f("ix_automation_schedules_schedule_key"), "automation_schedules", ["schedule_key"])
    op.create_index(op.f("ix_automation_schedules_schedule_type"), "automation_schedules", ["schedule_type"])
    op.create_index(op.f("ix_automation_schedules_schedule_status"), "automation_schedules", ["schedule_status"])
    op.create_index(op.f("ix_automation_schedules_schedule_checksum"), "automation_schedules", ["schedule_checksum"])

    op.create_table(
        "automation_triggers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("trigger_key", sa.String(length=120), nullable=False),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("trigger_status", sa.String(length=24), nullable=False),
        sa.Column("source_event_type", sa.String(length=80), nullable=False),
        sa.Column("source_record_type", sa.String(length=80), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("trigger_payload_json", sa.JSON(), nullable=False),
        sa.Column("trigger_checksum", sa.String(length=64), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "trigger_checksum", name="uq_automation_trigger_owner_checksum"),
    )
    op.create_index("ix_automation_trigger_status_created", "automation_triggers", ["trigger_status", "created_at", "id"])
    op.create_index("ix_automation_trigger_owner_created", "automation_triggers", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_triggers_owner_user_id"), "automation_triggers", ["owner_user_id"])
    op.create_index(op.f("ix_automation_triggers_organization_id"), "automation_triggers", ["organization_id"])
    op.create_index(op.f("ix_automation_triggers_trigger_key"), "automation_triggers", ["trigger_key"])
    op.create_index(op.f("ix_automation_triggers_trigger_type"), "automation_triggers", ["trigger_type"])
    op.create_index(op.f("ix_automation_triggers_trigger_status"), "automation_triggers", ["trigger_status"])
    op.create_index(op.f("ix_automation_triggers_source_event_type"), "automation_triggers", ["source_event_type"])
    op.create_index(op.f("ix_automation_triggers_source_record_type"), "automation_triggers", ["source_record_type"])
    op.create_index(op.f("ix_automation_triggers_source_record_id"), "automation_triggers", ["source_record_id"])
    op.create_index(op.f("ix_automation_triggers_source_checksum"), "automation_triggers", ["source_checksum"])
    op.create_index(op.f("ix_automation_triggers_trigger_checksum"), "automation_triggers", ["trigger_checksum"])

    op.create_table(
        "automation_workflows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("workflow_key", sa.String(length=120), nullable=False),
        sa.Column("workflow_name", sa.String(length=160), nullable=False),
        sa.Column("workflow_status", sa.String(length=24), nullable=False),
        sa.Column("workflow_category", sa.String(length=40), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("deterministic_ordering_enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "workflow_key", name="uq_automation_workflow_owner_key"),
    )
    op.create_index("ix_automation_workflow_status_created", "automation_workflows", ["workflow_status", "created_at", "id"])
    op.create_index("ix_automation_workflow_owner_created", "automation_workflows", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_automation_workflows_owner_user_id"), "automation_workflows", ["owner_user_id"])
    op.create_index(op.f("ix_automation_workflows_organization_id"), "automation_workflows", ["organization_id"])
    op.create_index(op.f("ix_automation_workflows_workflow_key"), "automation_workflows", ["workflow_key"])
    op.create_index(op.f("ix_automation_workflows_workflow_status"), "automation_workflows", ["workflow_status"])
    op.create_index(op.f("ix_automation_workflows_workflow_category"), "automation_workflows", ["workflow_category"])

    op.create_table(
        "automation_workflow_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_rank", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("dependency_mode", sa.String(length=24), nullable=False),
        sa.Column("delay_seconds", sa.Integer(), nullable=True),
        sa.Column("required_success", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["automation_workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "step_rank", name="uq_automation_workflow_step_rank"),
        sa.UniqueConstraint("workflow_id", "step_key", name="uq_automation_workflow_step_key"),
    )
    op.create_index("ix_automation_workflow_step_workflow_rank", "automation_workflow_steps", ["workflow_id", "step_rank", "id"])
    op.create_index(op.f("ix_automation_workflow_steps_workflow_id"), "automation_workflow_steps", ["workflow_id"])
    op.create_index(op.f("ix_automation_workflow_steps_step_rank"), "automation_workflow_steps", ["step_rank"])
    op.create_index(op.f("ix_automation_workflow_steps_step_key"), "automation_workflow_steps", ["step_key"])
    op.create_index(op.f("ix_automation_workflow_steps_job_type"), "automation_workflow_steps", ["job_type"])
    op.create_index(op.f("ix_automation_workflow_steps_dependency_mode"), "automation_workflow_steps", ["dependency_mode"])

    op.create_table(
        "automation_workflow_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("trigger_id", sa.Integer(), nullable=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("execution_status", sa.String(length=24), nullable=False),
        sa.Column("execution_checksum", sa.String(length=64), nullable=False),
        sa.Column("execution_manifest_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["automation_workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_id"], ["automation_triggers.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["automation_schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_checksum", name="uq_automation_workflow_execution_checksum"),
    )
    op.create_index("ix_automation_workflow_exec_workflow_created", "automation_workflow_executions", ["workflow_id", "created_at", "id"])
    op.create_index("ix_automation_workflow_exec_status_created", "automation_workflow_executions", ["execution_status", "created_at", "id"])
    op.create_index(op.f("ix_automation_workflow_executions_workflow_id"), "automation_workflow_executions", ["workflow_id"])
    op.create_index(op.f("ix_automation_workflow_executions_trigger_id"), "automation_workflow_executions", ["trigger_id"])
    op.create_index(op.f("ix_automation_workflow_executions_schedule_id"), "automation_workflow_executions", ["schedule_id"])
    op.create_index(op.f("ix_automation_workflow_executions_execution_status"), "automation_workflow_executions", ["execution_status"])
    op.create_index(op.f("ix_automation_workflow_executions_execution_checksum"), "automation_workflow_executions", ["execution_checksum"])

    op.create_table(
        "automation_workflow_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["automation_workflows.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["automation_workflow_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "issue_checksum", name="uq_automation_workflow_issue_checksum"),
    )
    op.create_index("ix_automation_workflow_issue_workflow_created", "automation_workflow_issues", ["workflow_id", "created_at", "id"])
    op.create_index("ix_automation_workflow_issue_type_created", "automation_workflow_issues", ["issue_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_workflow_issues_workflow_id"), "automation_workflow_issues", ["workflow_id"])
    op.create_index(op.f("ix_automation_workflow_issues_execution_id"), "automation_workflow_issues", ["execution_id"])
    op.create_index(op.f("ix_automation_workflow_issues_issue_type"), "automation_workflow_issues", ["issue_type"])
    op.create_index(op.f("ix_automation_workflow_issues_severity"), "automation_workflow_issues", ["severity"])
    op.create_index(op.f("ix_automation_workflow_issues_issue_checksum"), "automation_workflow_issues", ["issue_checksum"])

    op.create_table(
        "automation_workflow_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["automation_workflows.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["automation_workflow_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "event_checksum", name="uq_automation_workflow_history_checksum"),
    )
    op.create_index("ix_automation_workflow_history_workflow_created", "automation_workflow_history", ["workflow_id", "created_at", "id"])
    op.create_index("ix_automation_workflow_history_type_created", "automation_workflow_history", ["event_type", "created_at", "id"])
    op.create_index(op.f("ix_automation_workflow_history_workflow_id"), "automation_workflow_history", ["workflow_id"])
    op.create_index(op.f("ix_automation_workflow_history_execution_id"), "automation_workflow_history", ["execution_id"])
    op.create_index(op.f("ix_automation_workflow_history_event_type"), "automation_workflow_history", ["event_type"])
    op.create_index(op.f("ix_automation_workflow_history_from_status"), "automation_workflow_history", ["from_status"])
    op.create_index(op.f("ix_automation_workflow_history_to_status"), "automation_workflow_history", ["to_status"])
    op.create_index(op.f("ix_automation_workflow_history_event_checksum"), "automation_workflow_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_workflow_history_event_checksum"), table_name="automation_workflow_history")
    op.drop_index(op.f("ix_automation_workflow_history_to_status"), table_name="automation_workflow_history")
    op.drop_index(op.f("ix_automation_workflow_history_from_status"), table_name="automation_workflow_history")
    op.drop_index(op.f("ix_automation_workflow_history_event_type"), table_name="automation_workflow_history")
    op.drop_index(op.f("ix_automation_workflow_history_execution_id"), table_name="automation_workflow_history")
    op.drop_index(op.f("ix_automation_workflow_history_workflow_id"), table_name="automation_workflow_history")
    op.drop_index("ix_automation_workflow_history_type_created", table_name="automation_workflow_history")
    op.drop_index("ix_automation_workflow_history_workflow_created", table_name="automation_workflow_history")
    op.drop_table("automation_workflow_history")

    op.drop_index(op.f("ix_automation_workflow_issues_issue_checksum"), table_name="automation_workflow_issues")
    op.drop_index(op.f("ix_automation_workflow_issues_severity"), table_name="automation_workflow_issues")
    op.drop_index(op.f("ix_automation_workflow_issues_issue_type"), table_name="automation_workflow_issues")
    op.drop_index(op.f("ix_automation_workflow_issues_execution_id"), table_name="automation_workflow_issues")
    op.drop_index(op.f("ix_automation_workflow_issues_workflow_id"), table_name="automation_workflow_issues")
    op.drop_index("ix_automation_workflow_issue_type_created", table_name="automation_workflow_issues")
    op.drop_index("ix_automation_workflow_issue_workflow_created", table_name="automation_workflow_issues")
    op.drop_table("automation_workflow_issues")

    op.drop_index(op.f("ix_automation_workflow_executions_execution_checksum"), table_name="automation_workflow_executions")
    op.drop_index(op.f("ix_automation_workflow_executions_execution_status"), table_name="automation_workflow_executions")
    op.drop_index(op.f("ix_automation_workflow_executions_schedule_id"), table_name="automation_workflow_executions")
    op.drop_index(op.f("ix_automation_workflow_executions_trigger_id"), table_name="automation_workflow_executions")
    op.drop_index(op.f("ix_automation_workflow_executions_workflow_id"), table_name="automation_workflow_executions")
    op.drop_index("ix_automation_workflow_exec_status_created", table_name="automation_workflow_executions")
    op.drop_index("ix_automation_workflow_exec_workflow_created", table_name="automation_workflow_executions")
    op.drop_table("automation_workflow_executions")

    op.drop_index(op.f("ix_automation_workflow_steps_dependency_mode"), table_name="automation_workflow_steps")
    op.drop_index(op.f("ix_automation_workflow_steps_job_type"), table_name="automation_workflow_steps")
    op.drop_index(op.f("ix_automation_workflow_steps_step_key"), table_name="automation_workflow_steps")
    op.drop_index(op.f("ix_automation_workflow_steps_step_rank"), table_name="automation_workflow_steps")
    op.drop_index(op.f("ix_automation_workflow_steps_workflow_id"), table_name="automation_workflow_steps")
    op.drop_index("ix_automation_workflow_step_workflow_rank", table_name="automation_workflow_steps")
    op.drop_table("automation_workflow_steps")

    op.drop_index(op.f("ix_automation_workflows_workflow_category"), table_name="automation_workflows")
    op.drop_index(op.f("ix_automation_workflows_workflow_status"), table_name="automation_workflows")
    op.drop_index(op.f("ix_automation_workflows_workflow_key"), table_name="automation_workflows")
    op.drop_index(op.f("ix_automation_workflows_organization_id"), table_name="automation_workflows")
    op.drop_index(op.f("ix_automation_workflows_owner_user_id"), table_name="automation_workflows")
    op.drop_index("ix_automation_workflow_owner_created", table_name="automation_workflows")
    op.drop_index("ix_automation_workflow_status_created", table_name="automation_workflows")
    op.drop_table("automation_workflows")

    op.drop_index(op.f("ix_automation_triggers_trigger_checksum"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_source_checksum"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_source_record_id"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_source_record_type"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_source_event_type"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_trigger_status"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_trigger_type"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_trigger_key"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_organization_id"), table_name="automation_triggers")
    op.drop_index(op.f("ix_automation_triggers_owner_user_id"), table_name="automation_triggers")
    op.drop_index("ix_automation_trigger_owner_created", table_name="automation_triggers")
    op.drop_index("ix_automation_trigger_status_created", table_name="automation_triggers")
    op.drop_table("automation_triggers")

    op.drop_index(op.f("ix_automation_schedules_schedule_checksum"), table_name="automation_schedules")
    op.drop_index(op.f("ix_automation_schedules_schedule_status"), table_name="automation_schedules")
    op.drop_index(op.f("ix_automation_schedules_schedule_type"), table_name="automation_schedules")
    op.drop_index(op.f("ix_automation_schedules_schedule_key"), table_name="automation_schedules")
    op.drop_index(op.f("ix_automation_schedules_organization_id"), table_name="automation_schedules")
    op.drop_index(op.f("ix_automation_schedules_owner_user_id"), table_name="automation_schedules")
    op.drop_index("ix_automation_schedule_owner_created", table_name="automation_schedules")
    op.drop_index("ix_automation_schedule_status_next", table_name="automation_schedules")
    op.drop_table("automation_schedules")
