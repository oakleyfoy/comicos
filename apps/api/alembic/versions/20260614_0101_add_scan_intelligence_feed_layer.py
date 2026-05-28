"""add scan intelligence feed layer

Revision ID: 20260614_0101
Revises: 20260612_0100
Create Date: 2026-06-14 09:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260614_0101"
down_revision = "20260612_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_intelligence_feed_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("upload_session_id", sa.Integer(), nullable=True),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=True),
        sa.Column("normalization_run_id", sa.Integer(), nullable=True),
        sa.Column("boundary_run_id", sa.Integer(), nullable=True),
        sa.Column("ocr_run_id", sa.Integer(), nullable=True),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("defect_run_id", sa.Integer(), nullable=True),
        sa.Column("spine_tick_run_id", sa.Integer(), nullable=True),
        sa.Column("corner_edge_run_id", sa.Integer(), nullable=True),
        sa.Column("surface_defect_run_id", sa.Integer(), nullable=True),
        sa.Column("structural_damage_run_id", sa.Integer(), nullable=True),
        sa.Column("defect_aggregation_run_id", sa.Integer(), nullable=True),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=True),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=True),
        sa.Column("review_session_id", sa.Integer(), nullable=True),
        sa.Column("historical_comparison_run_id", sa.Integer(), nullable=True),
        sa.Column("authentication_run_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("feed_checksum", sa.String(length=64), nullable=False),
        sa.Column("feed_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("total_issues", sa.Integer(), nullable=False),
        sa.Column("review_required_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["upload_session_id"], ["scan_upload_session.id"]),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["scan_ingestion_batch.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["spine_tick_run_id"], ["scan_spine_tick_run.id"]),
        sa.ForeignKeyConstraint(["corner_edge_run_id"], ["scan_corner_edge_run.id"]),
        sa.ForeignKeyConstraint(["surface_defect_run_id"], ["scan_surface_defect_run.id"]),
        sa.ForeignKeyConstraint(["structural_damage_run_id"], ["scan_structural_damage_run.id"]),
        sa.ForeignKeyConstraint(["defect_aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.ForeignKeyConstraint(["review_session_id"], ["scan_review_session.id"]),
        sa.ForeignKeyConstraint(["historical_comparison_run_id"], ["scan_historical_comparison_runs.id"]),
        sa.ForeignKeyConstraint(["authentication_run_id"], ["scan_authentication_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "feed_checksum", name="uq_scan_feed_run_owner_checksum"),
    )
    op.create_index("ix_scan_feed_run_owner_created", "scan_intelligence_feed_runs", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_feed_run_owner_status", "scan_intelligence_feed_runs", ["owner_user_id", "feed_status", "id"], unique=False)
    op.create_index("ix_scan_feed_run_scan_image", "scan_intelligence_feed_runs", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_intelligence_feed_runs_feed_checksum", "scan_intelligence_feed_runs", ["feed_checksum"], unique=False)
    op.create_index("ix_scan_intelligence_feed_runs_feed_status", "scan_intelligence_feed_runs", ["feed_status"], unique=False)

    op.create_table(
        "scan_intelligence_feed_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("event_rank", sa.Integer(), nullable=False),
        sa.Column("timeline_rank", sa.Integer(), nullable=False),
        sa.Column("event_category", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("source_system", sa.String(length=48), nullable=False),
        sa.Column("event_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("lineage_checksum", sa.String(length=64), nullable=True),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["feed_run_id"], ["scan_intelligence_feed_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_run_id", "event_key", name="uq_scan_feed_event_run_key"),
    )
    op.create_index("ix_scan_feed_event_owner_created", "scan_intelligence_feed_events", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_feed_event_run_rank", "scan_intelligence_feed_events", ["feed_run_id", "event_rank", "id"], unique=False)
    op.create_index("ix_scan_feed_event_run_timeline", "scan_intelligence_feed_events", ["feed_run_id", "timeline_rank", "id"], unique=False)
    op.create_index("ix_scan_feed_event_owner_severity", "scan_intelligence_feed_events", ["owner_user_id", "severity", "id"], unique=False)
    op.create_index("ix_scan_intelligence_feed_events_event_category", "scan_intelligence_feed_events", ["event_category"], unique=False)
    op.create_index("ix_scan_intelligence_feed_events_source_system", "scan_intelligence_feed_events", ["source_system"], unique=False)
    op.create_index("ix_scan_intelligence_feed_events_event_key", "scan_intelligence_feed_events", ["event_key"], unique=False)

    op.create_table(
        "scan_intelligence_feed_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["feed_run_id"], ["scan_intelligence_feed_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_run_id", "artifact_type", "artifact_checksum", name="uq_scan_feed_art_run_type_checksum"),
    )
    op.create_index("ix_scan_feed_art_owner_created", "scan_intelligence_feed_artifacts", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_feed_art_run_type", "scan_intelligence_feed_artifacts", ["feed_run_id", "artifact_type", "id"], unique=False)
    op.create_index("ix_scan_intelligence_feed_artifacts_artifact_checksum", "scan_intelligence_feed_artifacts", ["artifact_checksum"], unique=False)

    op.create_table(
        "scan_intelligence_feed_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("source_system", sa.String(length=48), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["feed_run_id"], ["scan_intelligence_feed_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_run_id", "issue_checksum", name="uq_scan_feed_issue_run_checksum"),
    )
    op.create_index("ix_scan_feed_issue_owner_created", "scan_intelligence_feed_issues", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_feed_issue_run_type", "scan_intelligence_feed_issues", ["feed_run_id", "issue_type", "id"], unique=False)
    op.create_index("ix_scan_intelligence_feed_issues_issue_checksum", "scan_intelligence_feed_issues", ["issue_checksum"], unique=False)
    op.create_index("ix_scan_intelligence_feed_issues_source_system", "scan_intelligence_feed_issues", ["source_system"], unique=False)

    op.create_table(
        "scan_intelligence_feed_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["feed_run_id"], ["scan_intelligence_feed_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_run_id", "event_checksum", name="uq_scan_feed_history_run_checksum"),
    )
    op.create_index("ix_scan_feed_hist_owner_created", "scan_intelligence_feed_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_feed_hist_run_type", "scan_intelligence_feed_history", ["feed_run_id", "event_type", "id"], unique=False)
    op.create_index("ix_scan_intelligence_feed_history_event_checksum", "scan_intelligence_feed_history", ["event_checksum"], unique=False)


def downgrade() -> None:
    op.drop_table("scan_intelligence_feed_history")
    op.drop_table("scan_intelligence_feed_issues")
    op.drop_table("scan_intelligence_feed_artifacts")
    op.drop_table("scan_intelligence_feed_events")
    op.drop_table("scan_intelligence_feed_runs")
