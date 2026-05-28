"""add scan historical comparison engine

Revision ID: 20260611_0099
Revises: 20260610_0098
Create Date: 2026-06-11 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260611_0099"
down_revision = "20260610_0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_historical_comparison_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=True),
        sa.Column("review_session_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("historical_comparison_checksum", sa.String(length=64), nullable=False),
        sa.Column("comparison_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "historical_comparison_checksum", name="uq_scan_hist_comp_run_owner_checksum"),
    )
    op.create_index("ix_scan_historical_comparison_runs_owner_user_id", "scan_historical_comparison_runs", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_scan_image_id", "scan_historical_comparison_runs", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_reconciliation_run_id", "scan_historical_comparison_runs", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_visual_evidence_run_id", "scan_historical_comparison_runs", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_review_session_id", "scan_historical_comparison_runs", ["review_session_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_source_checksum", "scan_historical_comparison_runs", ["source_checksum"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_historical_comparison_checksum", "scan_historical_comparison_runs", ["historical_comparison_checksum"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_comparison_status", "scan_historical_comparison_runs", ["comparison_status"], unique=False)
    op.create_index("ix_scan_historical_comparison_runs_engine_version", "scan_historical_comparison_runs", ["engine_version"], unique=False)
    op.create_index("ix_scan_hist_comp_run_owner_created", "scan_historical_comparison_runs", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_run_owner_status", "scan_historical_comparison_runs", ["owner_user_id", "comparison_status", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_run_scan_image", "scan_historical_comparison_runs", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_historical_comparison_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_run_id", sa.Integer(), nullable=False),
        sa.Column("current_scan_image_id", sa.Integer(), nullable=False),
        sa.Column("prior_scan_image_id", sa.Integer(), nullable=False),
        sa.Column("current_identity_key", sa.String(length=1024), nullable=False),
        sa.Column("prior_identity_key", sa.String(length=1024), nullable=False),
        sa.Column("match_basis", sa.String(length=40), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("current_checksum", sa.String(length=64), nullable=False),
        sa.Column("prior_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["current_scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["prior_scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_historical_comparison_pairs_owner_user_id", "scan_historical_comparison_pairs", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_comparison_run_id", "scan_historical_comparison_pairs", ["comparison_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_current_scan_image_id", "scan_historical_comparison_pairs", ["current_scan_image_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_prior_scan_image_id", "scan_historical_comparison_pairs", ["prior_scan_image_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_current_identity_key", "scan_historical_comparison_pairs", ["current_identity_key"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_prior_identity_key", "scan_historical_comparison_pairs", ["prior_identity_key"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_match_basis", "scan_historical_comparison_pairs", ["match_basis"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_match_confidence", "scan_historical_comparison_pairs", ["match_confidence"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_current_checksum", "scan_historical_comparison_pairs", ["current_checksum"], unique=False)
    op.create_index("ix_scan_historical_comparison_pairs_prior_checksum", "scan_historical_comparison_pairs", ["prior_checksum"], unique=False)
    op.create_index("ix_scan_hist_comp_pair_owner_created", "scan_historical_comparison_pairs", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_pair_run_current_prior", "scan_historical_comparison_pairs", ["comparison_run_id", "current_scan_image_id", "prior_scan_image_id", "id"], unique=False)

    op.create_table(
        "scan_historical_comparison_deltas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_run_id", sa.Integer(), nullable=False),
        sa.Column("pair_id", sa.Integer(), nullable=False),
        sa.Column("delta_rank", sa.Integer(), nullable=False),
        sa.Column("delta_type", sa.String(length=32), nullable=False),
        sa.Column("delta_category", sa.String(length=24), nullable=False),
        sa.Column("delta_direction", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("severity_hint", sa.String(length=16), nullable=False),
        sa.Column("region_type", sa.String(length=40), nullable=True),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["pair_id"], ["scan_historical_comparison_pairs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_historical_comparison_deltas_owner_user_id", "scan_historical_comparison_deltas", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_comparison_run_id", "scan_historical_comparison_deltas", ["comparison_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_pair_id", "scan_historical_comparison_deltas", ["pair_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_delta_rank", "scan_historical_comparison_deltas", ["delta_rank"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_delta_type", "scan_historical_comparison_deltas", ["delta_type"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_delta_category", "scan_historical_comparison_deltas", ["delta_category"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_delta_direction", "scan_historical_comparison_deltas", ["delta_direction"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_confidence_score", "scan_historical_comparison_deltas", ["confidence_score"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_severity_hint", "scan_historical_comparison_deltas", ["severity_hint"], unique=False)
    op.create_index("ix_scan_historical_comparison_deltas_region_type", "scan_historical_comparison_deltas", ["region_type"], unique=False)
    op.create_index("ix_scan_hist_comp_delta_owner_created", "scan_historical_comparison_deltas", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_delta_run_pair_rank", "scan_historical_comparison_deltas", ["comparison_run_id", "pair_id", "delta_rank", "id"], unique=False)

    op.create_table(
        "scan_historical_comparison_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comparison_run_id", "artifact_type", "artifact_checksum", name="uq_scan_hist_comp_art_run_type_checksum"),
    )
    op.create_index("ix_scan_historical_comparison_artifacts_owner_user_id", "scan_historical_comparison_artifacts", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_artifacts_comparison_run_id", "scan_historical_comparison_artifacts", ["comparison_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_artifacts_artifact_type", "scan_historical_comparison_artifacts", ["artifact_type"], unique=False)
    op.create_index("ix_scan_historical_comparison_artifacts_storage_backend", "scan_historical_comparison_artifacts", ["storage_backend"], unique=False)
    op.create_index("ix_scan_historical_comparison_artifacts_artifact_checksum", "scan_historical_comparison_artifacts", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_hist_comp_art_owner_created", "scan_historical_comparison_artifacts", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_art_run_type", "scan_historical_comparison_artifacts", ["comparison_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_historical_comparison_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_historical_comparison_issues_owner_user_id", "scan_historical_comparison_issues", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_issues_comparison_run_id", "scan_historical_comparison_issues", ["comparison_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_issues_issue_type", "scan_historical_comparison_issues", ["issue_type"], unique=False)
    op.create_index("ix_scan_historical_comparison_issues_severity", "scan_historical_comparison_issues", ["severity"], unique=False)
    op.create_index("ix_scan_hist_comp_issue_owner_created", "scan_historical_comparison_issues", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_issue_run_type", "scan_historical_comparison_issues", ["comparison_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_historical_comparison_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("comparison_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_historical_comparison_history_owner_user_id", "scan_historical_comparison_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_history_comparison_run_id", "scan_historical_comparison_history", ["comparison_run_id"], unique=False)
    op.create_index("ix_scan_historical_comparison_history_event_type", "scan_historical_comparison_history", ["event_type"], unique=False)
    op.create_index("ix_scan_historical_comparison_history_event_checksum", "scan_historical_comparison_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_hist_comp_hist_owner_created", "scan_historical_comparison_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_hist_comp_hist_run_type", "scan_historical_comparison_history", ["comparison_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_table("scan_historical_comparison_history")
    op.drop_table("scan_historical_comparison_issues")
    op.drop_table("scan_historical_comparison_artifacts")
    op.drop_table("scan_historical_comparison_deltas")
    op.drop_table("scan_historical_comparison_pairs")
    op.drop_table("scan_historical_comparison_runs")
