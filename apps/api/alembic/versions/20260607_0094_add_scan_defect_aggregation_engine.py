"""add scan defect aggregation engine

Revision ID: 20260607_0095
Revises: 20260606_0094
Create Date: 2026-06-07 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0095"
down_revision = "20260606_0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_defect_aggregation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("aggregation_checksum", sa.String(length=64), nullable=False),
        sa.Column("aggregation_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "aggregation_checksum", name="uq_scan_defect_aggregation_run_owner_checksum"),
    )
    op.create_index("ix_scan_defect_aggregation_run_owner_user_id", "scan_defect_aggregation_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_scan_image_id", "scan_defect_aggregation_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_source_checksum", "scan_defect_aggregation_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_aggregation_checksum", "scan_defect_aggregation_run", ["aggregation_checksum"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_aggregation_status", "scan_defect_aggregation_run", ["aggregation_status"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_engine_version", "scan_defect_aggregation_run", ["engine_version"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_owner_created", "scan_defect_aggregation_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_run_scan_image", "scan_defect_aggregation_run", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_defect_aggregate_cluster",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("cluster_rank", sa.Integer(), nullable=False),
        sa.Column("cluster_type", sa.String(length=32), nullable=False),
        sa.Column("cluster_region", sa.String(length=32), nullable=False),
        sa.Column("cluster_confidence", sa.Float(), nullable=False),
        sa.Column("aggregate_severity_hint", sa.String(length=16), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("cluster_area_ratio", sa.Float(), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_aggregate_cluster_owner_user_id", "scan_defect_aggregate_cluster", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_aggregation_run_id", "scan_defect_aggregate_cluster", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_cluster_rank", "scan_defect_aggregate_cluster", ["cluster_rank"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_cluster_type", "scan_defect_aggregate_cluster", ["cluster_type"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_cluster_region", "scan_defect_aggregate_cluster", ["cluster_region"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_cluster_confidence", "scan_defect_aggregate_cluster", ["cluster_confidence"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_aggregate_severity_hint", "scan_defect_aggregate_cluster", ["aggregate_severity_hint"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_owner_created", "scan_defect_aggregate_cluster", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_cluster_run_rank", "scan_defect_aggregate_cluster", ["aggregation_run_id", "cluster_rank", "id"], unique=False)

    op.create_table(
        "scan_defect_aggregate_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("source_detector", sa.String(length=32), nullable=False),
        sa.Column("source_evidence_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("contribution_weight", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["cluster_id"], ["scan_defect_aggregate_cluster.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_aggregate_evidence_owner_user_id", "scan_defect_aggregate_evidence", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_aggregation_run_id", "scan_defect_aggregate_evidence", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_cluster_id", "scan_defect_aggregate_evidence", ["cluster_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_source_detector", "scan_defect_aggregate_evidence", ["source_detector"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_source_evidence_id", "scan_defect_aggregate_evidence", ["source_evidence_id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_evidence_type", "scan_defect_aggregate_evidence", ["evidence_type"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_confidence_score", "scan_defect_aggregate_evidence", ["confidence_score"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_owner_created", "scan_defect_aggregate_evidence", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_run_cluster", "scan_defect_aggregate_evidence", ["aggregation_run_id", "cluster_id", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregate_evidence_source", "scan_defect_aggregate_evidence", ["aggregation_run_id", "source_detector", "source_evidence_id"], unique=False)

    op.create_table(
        "scan_defect_aggregation_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aggregation_run_id", "artifact_type", "artifact_checksum", name="uq_scan_defect_aggregation_art_run_type_checksum"),
    )
    op.create_index("ix_scan_defect_aggregation_artifact_owner_user_id", "scan_defect_aggregation_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_artifact_aggregation_run_id", "scan_defect_aggregation_artifact", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_artifact_artifact_type", "scan_defect_aggregation_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_defect_aggregation_artifact_storage_backend", "scan_defect_aggregation_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_defect_aggregation_artifact_artifact_checksum", "scan_defect_aggregation_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_defect_aggregation_art_owner_created", "scan_defect_aggregation_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_art_run_type", "scan_defect_aggregation_artifact", ["aggregation_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_defect_aggregation_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_aggregation_issue_owner_user_id", "scan_defect_aggregation_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_issue_aggregation_run_id", "scan_defect_aggregation_issue", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_issue_issue_type", "scan_defect_aggregation_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_defect_aggregation_issue_severity", "scan_defect_aggregation_issue", ["severity"], unique=False)
    op.create_index("ix_scan_defect_aggregation_issue_owner_created", "scan_defect_aggregation_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_issue_run_type", "scan_defect_aggregation_issue", ["aggregation_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_defect_aggregation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_aggregation_history_owner_user_id", "scan_defect_aggregation_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_history_aggregation_run_id", "scan_defect_aggregation_history", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_history_event_type", "scan_defect_aggregation_history", ["event_type"], unique=False)
    op.create_index("ix_scan_defect_aggregation_history_event_checksum", "scan_defect_aggregation_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_defect_aggregation_hist_owner_created", "scan_defect_aggregation_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_aggregation_hist_run_type", "scan_defect_aggregation_history", ["aggregation_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_defect_aggregation_hist_run_type", table_name="scan_defect_aggregation_history")
    op.drop_index("ix_scan_defect_aggregation_hist_owner_created", table_name="scan_defect_aggregation_history")
    op.drop_index("ix_scan_defect_aggregation_history_event_checksum", table_name="scan_defect_aggregation_history")
    op.drop_index("ix_scan_defect_aggregation_history_event_type", table_name="scan_defect_aggregation_history")
    op.drop_index("ix_scan_defect_aggregation_history_aggregation_run_id", table_name="scan_defect_aggregation_history")
    op.drop_index("ix_scan_defect_aggregation_history_owner_user_id", table_name="scan_defect_aggregation_history")
    op.drop_table("scan_defect_aggregation_history")

    op.drop_index("ix_scan_defect_aggregation_issue_run_type", table_name="scan_defect_aggregation_issue")
    op.drop_index("ix_scan_defect_aggregation_issue_owner_created", table_name="scan_defect_aggregation_issue")
    op.drop_index("ix_scan_defect_aggregation_issue_severity", table_name="scan_defect_aggregation_issue")
    op.drop_index("ix_scan_defect_aggregation_issue_issue_type", table_name="scan_defect_aggregation_issue")
    op.drop_index("ix_scan_defect_aggregation_issue_aggregation_run_id", table_name="scan_defect_aggregation_issue")
    op.drop_index("ix_scan_defect_aggregation_issue_owner_user_id", table_name="scan_defect_aggregation_issue")
    op.drop_table("scan_defect_aggregation_issue")

    op.drop_index("ix_scan_defect_aggregation_art_run_type", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_art_owner_created", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_artifact_artifact_checksum", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_artifact_storage_backend", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_artifact_artifact_type", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_artifact_aggregation_run_id", table_name="scan_defect_aggregation_artifact")
    op.drop_index("ix_scan_defect_aggregation_artifact_owner_user_id", table_name="scan_defect_aggregation_artifact")
    op.drop_table("scan_defect_aggregation_artifact")

    op.drop_index("ix_scan_defect_aggregate_evidence_source", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_run_cluster", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_owner_created", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_confidence_score", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_evidence_type", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_source_evidence_id", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_source_detector", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_cluster_id", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_aggregation_run_id", table_name="scan_defect_aggregate_evidence")
    op.drop_index("ix_scan_defect_aggregate_evidence_owner_user_id", table_name="scan_defect_aggregate_evidence")
    op.drop_table("scan_defect_aggregate_evidence")

    op.drop_index("ix_scan_defect_aggregate_cluster_run_rank", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_owner_created", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_aggregate_severity_hint", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_cluster_confidence", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_cluster_region", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_cluster_type", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_cluster_rank", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_aggregation_run_id", table_name="scan_defect_aggregate_cluster")
    op.drop_index("ix_scan_defect_aggregate_cluster_owner_user_id", table_name="scan_defect_aggregate_cluster")
    op.drop_table("scan_defect_aggregate_cluster")

    op.drop_index("ix_scan_defect_aggregation_run_scan_image", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_owner_created", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_engine_version", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_aggregation_status", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_aggregation_checksum", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_source_checksum", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_scan_image_id", table_name="scan_defect_aggregation_run")
    op.drop_index("ix_scan_defect_aggregation_run_owner_user_id", table_name="scan_defect_aggregation_run")
    op.drop_table("scan_defect_aggregation_run")
