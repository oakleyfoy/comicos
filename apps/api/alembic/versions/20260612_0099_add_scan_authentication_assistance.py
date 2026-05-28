"""add scan authentication assistance

Revision ID: 20260612_0100
Revises: 20260611_0099
Create Date: 2026-06-12 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260612_0100"
down_revision = "20260611_0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_authentication_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=True),
        sa.Column("historical_comparison_run_id", sa.Integer(), nullable=True),
        sa.Column("review_session_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("authentication_checksum", sa.String(length=64), nullable=False),
        sa.Column("authentication_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("rubric_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.ForeignKeyConstraint(["historical_comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "authentication_checksum", name="uq_scan_auth_run_owner_checksum"),
    )
    op.create_index("ix_scan_authentication_runs_owner_user_id", "scan_authentication_runs", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_scan_image_id", "scan_authentication_runs", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_reconciliation_run_id", "scan_authentication_runs", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_visual_evidence_run_id", "scan_authentication_runs", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_historical_comparison_run_id", "scan_authentication_runs", ["historical_comparison_run_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_review_session_id", "scan_authentication_runs", ["review_session_id"], unique=False)
    op.create_index("ix_scan_authentication_runs_source_checksum", "scan_authentication_runs", ["source_checksum"], unique=False)
    op.create_index("ix_scan_authentication_runs_authentication_checksum", "scan_authentication_runs", ["authentication_checksum"], unique=False)
    op.create_index("ix_scan_authentication_runs_authentication_status", "scan_authentication_runs", ["authentication_status"], unique=False)
    op.create_index("ix_scan_authentication_runs_engine_version", "scan_authentication_runs", ["engine_version"], unique=False)
    op.create_index("ix_scan_authentication_runs_rubric_version", "scan_authentication_runs", ["rubric_version"], unique=False)
    op.create_index("ix_scan_auth_run_owner_created", "scan_authentication_runs", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_run_owner_status", "scan_authentication_runs", ["owner_user_id", "authentication_status", "id"], unique=False)
    op.create_index("ix_scan_auth_run_scan_image", "scan_authentication_runs", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_authentication_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authentication_run_id", sa.Integer(), nullable=False),
        sa.Column("signal_rank", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=40), nullable=False),
        sa.Column("signal_category", sa.String(length=24), nullable=False),
        sa.Column("signal_status", sa.String(length=40), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_authentication_signals_owner_user_id", "scan_authentication_signals", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_signals_authentication_run_id", "scan_authentication_signals", ["authentication_run_id"], unique=False)
    op.create_index("ix_scan_authentication_signals_signal_rank", "scan_authentication_signals", ["signal_rank"], unique=False)
    op.create_index("ix_scan_authentication_signals_signal_type", "scan_authentication_signals", ["signal_type"], unique=False)
    op.create_index("ix_scan_authentication_signals_signal_category", "scan_authentication_signals", ["signal_category"], unique=False)
    op.create_index("ix_scan_authentication_signals_signal_status", "scan_authentication_signals", ["signal_status"], unique=False)
    op.create_index("ix_scan_authentication_signals_confidence_score", "scan_authentication_signals", ["confidence_score"], unique=False)
    op.create_index("ix_scan_authentication_signals_source_system", "scan_authentication_signals", ["source_system"], unique=False)
    op.create_index("ix_scan_authentication_signals_source_record_id", "scan_authentication_signals", ["source_record_id"], unique=False)
    op.create_index("ix_scan_auth_signal_owner_created", "scan_authentication_signals", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_signal_run_rank", "scan_authentication_signals", ["authentication_run_id", "signal_rank", "id"], unique=False)

    op.create_table(
        "scan_authentication_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authentication_run_id", sa.Integer(), nullable=False),
        sa.Column("finding_rank", sa.Integer(), nullable=False),
        sa.Column("finding_type", sa.String(length=40), nullable=False),
        sa.Column("finding_status", sa.String(length=24), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("review_priority", sa.String(length=16), nullable=False),
        sa.Column("finding_text", sa.String(length=1024), nullable=False),
        sa.Column("source_signal_ids_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_authentication_findings_owner_user_id", "scan_authentication_findings", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_findings_authentication_run_id", "scan_authentication_findings", ["authentication_run_id"], unique=False)
    op.create_index("ix_scan_authentication_findings_finding_rank", "scan_authentication_findings", ["finding_rank"], unique=False)
    op.create_index("ix_scan_authentication_findings_finding_type", "scan_authentication_findings", ["finding_type"], unique=False)
    op.create_index("ix_scan_authentication_findings_finding_status", "scan_authentication_findings", ["finding_status"], unique=False)
    op.create_index("ix_scan_authentication_findings_confidence_score", "scan_authentication_findings", ["confidence_score"], unique=False)
    op.create_index("ix_scan_authentication_findings_review_priority", "scan_authentication_findings", ["review_priority"], unique=False)
    op.create_index("ix_scan_auth_finding_owner_created", "scan_authentication_findings", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_finding_run_rank", "scan_authentication_findings", ["authentication_run_id", "finding_rank", "id"], unique=False)

    op.create_table(
        "scan_authentication_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authentication_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authentication_run_id", "artifact_type", "artifact_checksum", name="uq_scan_auth_art_run_type_checksum"),
    )
    op.create_index("ix_scan_authentication_artifacts_owner_user_id", "scan_authentication_artifacts", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_artifacts_authentication_run_id", "scan_authentication_artifacts", ["authentication_run_id"], unique=False)
    op.create_index("ix_scan_authentication_artifacts_artifact_type", "scan_authentication_artifacts", ["artifact_type"], unique=False)
    op.create_index("ix_scan_authentication_artifacts_storage_backend", "scan_authentication_artifacts", ["storage_backend"], unique=False)
    op.create_index("ix_scan_authentication_artifacts_artifact_checksum", "scan_authentication_artifacts", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_auth_art_owner_created", "scan_authentication_artifacts", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_art_run_type", "scan_authentication_artifacts", ["authentication_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_authentication_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authentication_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_authentication_issues_owner_user_id", "scan_authentication_issues", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_issues_authentication_run_id", "scan_authentication_issues", ["authentication_run_id"], unique=False)
    op.create_index("ix_scan_authentication_issues_issue_type", "scan_authentication_issues", ["issue_type"], unique=False)
    op.create_index("ix_scan_authentication_issues_severity", "scan_authentication_issues", ["severity"], unique=False)
    op.create_index("ix_scan_auth_issue_owner_created", "scan_authentication_issues", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_issue_run_type", "scan_authentication_issues", ["authentication_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_authentication_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authentication_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_authentication_history_owner_user_id", "scan_authentication_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_authentication_history_authentication_run_id", "scan_authentication_history", ["authentication_run_id"], unique=False)
    op.create_index("ix_scan_authentication_history_event_type", "scan_authentication_history", ["event_type"], unique=False)
    op.create_index("ix_scan_authentication_history_event_checksum", "scan_authentication_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_auth_hist_owner_created", "scan_authentication_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_auth_hist_run_type", "scan_authentication_history", ["authentication_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_table("scan_authentication_history")
    op.drop_table("scan_authentication_issues")
    op.drop_table("scan_authentication_artifacts")
    op.drop_table("scan_authentication_findings")
    op.drop_table("scan_authentication_signals")
    op.drop_table("scan_authentication_runs")
