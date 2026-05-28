"""add scan replay layer

Revision ID: 20260614_0102
Revises: 20260614_0101
Create Date: 2026-06-14 00:10:02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260614_0102"
down_revision = "20260614_0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_replay_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=True),
        sa.Column("replay_scope", sa.String(length=40), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "replay_checksum", name="uq_scan_replay_run_owner_checksum"),
    )
    op.create_index("ix_scan_replay_run_owner_created", "scan_replay_runs", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_run_owner_status", "scan_replay_runs", ["owner_user_id", "replay_status", "id"])
    op.create_index("ix_scan_replay_run_scope", "scan_replay_runs", ["replay_scope", "created_at", "id"])
    op.create_index(op.f("ix_scan_replay_runs_owner_user_id"), "scan_replay_runs", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_runs_scan_image_id"), "scan_replay_runs", ["scan_image_id"])
    op.create_index(op.f("ix_scan_replay_runs_replay_scope"), "scan_replay_runs", ["replay_scope"])
    op.create_index(op.f("ix_scan_replay_runs_source_checksum"), "scan_replay_runs", ["source_checksum"])
    op.create_index(op.f("ix_scan_replay_runs_replay_checksum"), "scan_replay_runs", ["replay_checksum"])
    op.create_index(op.f("ix_scan_replay_runs_replay_status"), "scan_replay_runs", ["replay_status"])
    op.create_index(op.f("ix_scan_replay_runs_engine_version"), "scan_replay_runs", ["engine_version"])

    op.create_table(
        "scan_replay_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("step_rank", sa.Integer(), nullable=False),
        sa.Column("phase_key", sa.String(length=48), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("expected_checksum", sa.String(length=64), nullable=True),
        sa.Column("observed_checksum", sa.String(length=64), nullable=True),
        sa.Column("replay_step_status", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "phase_key", name="uq_scan_replay_step_run_phase"),
    )
    op.create_index("ix_scan_replay_step_owner_created", "scan_replay_steps", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_step_run_rank", "scan_replay_steps", ["replay_run_id", "step_rank", "id"])
    op.create_index(op.f("ix_scan_replay_steps_owner_user_id"), "scan_replay_steps", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_steps_replay_run_id"), "scan_replay_steps", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_steps_step_rank"), "scan_replay_steps", ["step_rank"])
    op.create_index(op.f("ix_scan_replay_steps_phase_key"), "scan_replay_steps", ["phase_key"])
    op.create_index(op.f("ix_scan_replay_steps_source_record_id"), "scan_replay_steps", ["source_record_id"])
    op.create_index(op.f("ix_scan_replay_steps_expected_checksum"), "scan_replay_steps", ["expected_checksum"])
    op.create_index(op.f("ix_scan_replay_steps_observed_checksum"), "scan_replay_steps", ["observed_checksum"])
    op.create_index(op.f("ix_scan_replay_steps_replay_step_status"), "scan_replay_steps", ["replay_step_status"])

    op.create_table(
        "scan_replay_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("check_type", sa.String(length=40), nullable=False),
        sa.Column("check_status", sa.String(length=16), nullable=False),
        sa.Column("expected_value", sa.String(length=2048), nullable=True),
        sa.Column("observed_value", sa.String(length=2048), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["scan_replay_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "step_id", "check_type", "expected_value", "observed_value", name="uq_scan_replay_check_run_step_type_values"),
    )
    op.create_index("ix_scan_replay_check_owner_created", "scan_replay_checks", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_check_run_type", "scan_replay_checks", ["replay_run_id", "check_type", "id"])
    op.create_index("ix_scan_replay_check_step_type", "scan_replay_checks", ["step_id", "check_type", "id"])
    op.create_index(op.f("ix_scan_replay_checks_owner_user_id"), "scan_replay_checks", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_checks_replay_run_id"), "scan_replay_checks", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_checks_step_id"), "scan_replay_checks", ["step_id"])
    op.create_index(op.f("ix_scan_replay_checks_check_type"), "scan_replay_checks", ["check_type"])
    op.create_index(op.f("ix_scan_replay_checks_check_status"), "scan_replay_checks", ["check_status"])

    op.create_table(
        "scan_replay_discrepancies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("discrepancy_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("expected_value", sa.String(length=2048), nullable=True),
        sa.Column("observed_value", sa.String(length=2048), nullable=True),
        sa.Column("discrepancy_message", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["scan_replay_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "step_id", "discrepancy_type", "expected_value", "observed_value", name="uq_scan_replay_disc_run_step_type_values"),
    )
    op.create_index("ix_scan_replay_disc_owner_created", "scan_replay_discrepancies", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_disc_run_severity", "scan_replay_discrepancies", ["replay_run_id", "severity", "id"])
    op.create_index("ix_scan_replay_disc_run_type", "scan_replay_discrepancies", ["replay_run_id", "discrepancy_type", "id"])
    op.create_index(op.f("ix_scan_replay_discrepancies_owner_user_id"), "scan_replay_discrepancies", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_discrepancies_replay_run_id"), "scan_replay_discrepancies", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_discrepancies_step_id"), "scan_replay_discrepancies", ["step_id"])
    op.create_index(op.f("ix_scan_replay_discrepancies_discrepancy_type"), "scan_replay_discrepancies", ["discrepancy_type"])
    op.create_index(op.f("ix_scan_replay_discrepancies_severity"), "scan_replay_discrepancies", ["severity"])

    op.create_table(
        "scan_replay_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "artifact_type", "artifact_checksum", name="uq_scan_replay_art_run_type_checksum"),
    )
    op.create_index("ix_scan_replay_art_owner_created", "scan_replay_artifacts", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_art_run_type", "scan_replay_artifacts", ["replay_run_id", "artifact_type", "id"])
    op.create_index(op.f("ix_scan_replay_artifacts_owner_user_id"), "scan_replay_artifacts", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_artifacts_replay_run_id"), "scan_replay_artifacts", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_artifacts_artifact_type"), "scan_replay_artifacts", ["artifact_type"])
    op.create_index(op.f("ix_scan_replay_artifacts_storage_backend"), "scan_replay_artifacts", ["storage_backend"])
    op.create_index(op.f("ix_scan_replay_artifacts_artifact_checksum"), "scan_replay_artifacts", ["artifact_checksum"])

    op.create_table(
        "scan_replay_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "issue_checksum", name="uq_scan_replay_issue_run_checksum"),
    )
    op.create_index("ix_scan_replay_issue_owner_created", "scan_replay_issues", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_issue_run_type", "scan_replay_issues", ["replay_run_id", "issue_type", "id"])
    op.create_index(op.f("ix_scan_replay_issues_owner_user_id"), "scan_replay_issues", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_issues_replay_run_id"), "scan_replay_issues", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_issues_issue_type"), "scan_replay_issues", ["issue_type"])
    op.create_index(op.f("ix_scan_replay_issues_severity"), "scan_replay_issues", ["severity"])
    op.create_index(op.f("ix_scan_replay_issues_issue_checksum"), "scan_replay_issues", ["issue_checksum"])

    op.create_table(
        "scan_replay_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "event_checksum", name="uq_scan_replay_history_run_checksum"),
    )
    op.create_index("ix_scan_replay_hist_owner_created", "scan_replay_history", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_scan_replay_hist_run_type", "scan_replay_history", ["replay_run_id", "event_type", "id"])
    op.create_index(op.f("ix_scan_replay_history_owner_user_id"), "scan_replay_history", ["owner_user_id"])
    op.create_index(op.f("ix_scan_replay_history_replay_run_id"), "scan_replay_history", ["replay_run_id"])
    op.create_index(op.f("ix_scan_replay_history_event_type"), "scan_replay_history", ["event_type"])
    op.create_index(op.f("ix_scan_replay_history_event_checksum"), "scan_replay_history", ["event_checksum"])


def downgrade() -> None:
    op.drop_index(op.f("ix_scan_replay_history_event_checksum"), table_name="scan_replay_history")
    op.drop_index(op.f("ix_scan_replay_history_event_type"), table_name="scan_replay_history")
    op.drop_index(op.f("ix_scan_replay_history_replay_run_id"), table_name="scan_replay_history")
    op.drop_index(op.f("ix_scan_replay_history_owner_user_id"), table_name="scan_replay_history")
    op.drop_index("ix_scan_replay_hist_run_type", table_name="scan_replay_history")
    op.drop_index("ix_scan_replay_hist_owner_created", table_name="scan_replay_history")
    op.drop_table("scan_replay_history")

    op.drop_index(op.f("ix_scan_replay_issues_issue_checksum"), table_name="scan_replay_issues")
    op.drop_index(op.f("ix_scan_replay_issues_severity"), table_name="scan_replay_issues")
    op.drop_index(op.f("ix_scan_replay_issues_issue_type"), table_name="scan_replay_issues")
    op.drop_index(op.f("ix_scan_replay_issues_replay_run_id"), table_name="scan_replay_issues")
    op.drop_index(op.f("ix_scan_replay_issues_owner_user_id"), table_name="scan_replay_issues")
    op.drop_index("ix_scan_replay_issue_run_type", table_name="scan_replay_issues")
    op.drop_index("ix_scan_replay_issue_owner_created", table_name="scan_replay_issues")
    op.drop_table("scan_replay_issues")

    op.drop_index(op.f("ix_scan_replay_artifacts_artifact_checksum"), table_name="scan_replay_artifacts")
    op.drop_index(op.f("ix_scan_replay_artifacts_storage_backend"), table_name="scan_replay_artifacts")
    op.drop_index(op.f("ix_scan_replay_artifacts_artifact_type"), table_name="scan_replay_artifacts")
    op.drop_index(op.f("ix_scan_replay_artifacts_replay_run_id"), table_name="scan_replay_artifacts")
    op.drop_index(op.f("ix_scan_replay_artifacts_owner_user_id"), table_name="scan_replay_artifacts")
    op.drop_index("ix_scan_replay_art_run_type", table_name="scan_replay_artifacts")
    op.drop_index("ix_scan_replay_art_owner_created", table_name="scan_replay_artifacts")
    op.drop_table("scan_replay_artifacts")

    op.drop_index(op.f("ix_scan_replay_discrepancies_severity"), table_name="scan_replay_discrepancies")
    op.drop_index(op.f("ix_scan_replay_discrepancies_discrepancy_type"), table_name="scan_replay_discrepancies")
    op.drop_index(op.f("ix_scan_replay_discrepancies_step_id"), table_name="scan_replay_discrepancies")
    op.drop_index(op.f("ix_scan_replay_discrepancies_replay_run_id"), table_name="scan_replay_discrepancies")
    op.drop_index(op.f("ix_scan_replay_discrepancies_owner_user_id"), table_name="scan_replay_discrepancies")
    op.drop_index("ix_scan_replay_disc_run_type", table_name="scan_replay_discrepancies")
    op.drop_index("ix_scan_replay_disc_run_severity", table_name="scan_replay_discrepancies")
    op.drop_index("ix_scan_replay_disc_owner_created", table_name="scan_replay_discrepancies")
    op.drop_table("scan_replay_discrepancies")

    op.drop_index(op.f("ix_scan_replay_checks_check_status"), table_name="scan_replay_checks")
    op.drop_index(op.f("ix_scan_replay_checks_check_type"), table_name="scan_replay_checks")
    op.drop_index(op.f("ix_scan_replay_checks_step_id"), table_name="scan_replay_checks")
    op.drop_index(op.f("ix_scan_replay_checks_replay_run_id"), table_name="scan_replay_checks")
    op.drop_index(op.f("ix_scan_replay_checks_owner_user_id"), table_name="scan_replay_checks")
    op.drop_index("ix_scan_replay_check_step_type", table_name="scan_replay_checks")
    op.drop_index("ix_scan_replay_check_run_type", table_name="scan_replay_checks")
    op.drop_index("ix_scan_replay_check_owner_created", table_name="scan_replay_checks")
    op.drop_table("scan_replay_checks")

    op.drop_index(op.f("ix_scan_replay_steps_replay_step_status"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_observed_checksum"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_expected_checksum"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_source_record_id"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_phase_key"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_step_rank"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_replay_run_id"), table_name="scan_replay_steps")
    op.drop_index(op.f("ix_scan_replay_steps_owner_user_id"), table_name="scan_replay_steps")
    op.drop_index("ix_scan_replay_step_run_rank", table_name="scan_replay_steps")
    op.drop_index("ix_scan_replay_step_owner_created", table_name="scan_replay_steps")
    op.drop_table("scan_replay_steps")

    op.drop_index(op.f("ix_scan_replay_runs_engine_version"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_replay_status"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_replay_checksum"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_source_checksum"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_replay_scope"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_scan_image_id"), table_name="scan_replay_runs")
    op.drop_index(op.f("ix_scan_replay_runs_owner_user_id"), table_name="scan_replay_runs")
    op.drop_index("ix_scan_replay_run_scope", table_name="scan_replay_runs")
    op.drop_index("ix_scan_replay_run_owner_status", table_name="scan_replay_runs")
    op.drop_index("ix_scan_replay_run_owner_created", table_name="scan_replay_runs")
    op.drop_table("scan_replay_runs")
