"""add scan corner edge engine

Revision ID: 20260604_0092
Revises: 20260603_0091
Create Date: 2026-06-04 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_0092"
down_revision = "20260603_0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_corner_edge_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("corner_edge_checksum", sa.String(length=64), nullable=False),
        sa.Column("detection_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "corner_edge_checksum", name="uq_scan_corner_edge_run_owner_checksum"),
    )
    op.create_index("ix_scan_corner_edge_run_owner_user_id", "scan_corner_edge_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_corner_edge_run_scan_image_id", "scan_corner_edge_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_corner_edge_run_defect_run_id", "scan_corner_edge_run", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_corner_edge_run_source_checksum", "scan_corner_edge_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_corner_edge_run_corner_edge_checksum", "scan_corner_edge_run", ["corner_edge_checksum"], unique=False)
    op.create_index("ix_scan_corner_edge_run_detection_status", "scan_corner_edge_run", ["detection_status"], unique=False)
    op.create_index("ix_scan_corner_edge_run_engine_version", "scan_corner_edge_run", ["engine_version"], unique=False)
    op.create_index("ix_scan_corner_edge_run_owner_created", "scan_corner_edge_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_run_scan_image", "scan_corner_edge_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_run_defect", "scan_corner_edge_run", ["defect_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_corner_edge_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("corner_edge_run_id", sa.Integer(), nullable=False),
        sa.Column("defect_evidence_id", sa.Integer(), nullable=True),
        sa.Column("evidence_rank", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("severity_hint", sa.String(length=16), nullable=False),
        sa.Column("region_type", sa.String(length=40), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("edge_distance_px", sa.Integer(), nullable=False),
        sa.Column("corner_overlap_ratio", sa.Float(), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corner_edge_run_id"], ["scan_corner_edge_run.id"]),
        sa.ForeignKeyConstraint(["defect_evidence_id"], ["scan_defect_evidence.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_corner_edge_evidence_owner_user_id", "scan_corner_edge_evidence", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_corner_edge_run_id", "scan_corner_edge_evidence", ["corner_edge_run_id"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_defect_evidence_id", "scan_corner_edge_evidence", ["defect_evidence_id"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_evidence_rank", "scan_corner_edge_evidence", ["evidence_rank"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_evidence_type", "scan_corner_edge_evidence", ["evidence_type"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_confidence_score", "scan_corner_edge_evidence", ["confidence_score"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_severity_hint", "scan_corner_edge_evidence", ["severity_hint"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_region_type", "scan_corner_edge_evidence", ["region_type"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_owner_created", "scan_corner_edge_evidence", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_run_rank", "scan_corner_edge_evidence", ["corner_edge_run_id", "evidence_rank", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_evidence_run_conf", "scan_corner_edge_evidence", ["corner_edge_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_corner_edge_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("corner_edge_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corner_edge_run_id"], ["scan_corner_edge_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corner_edge_run_id", "artifact_type", "artifact_checksum", name="uq_scan_corner_edge_art_run_type_checksum"),
    )
    op.create_index("ix_scan_corner_edge_artifact_owner_user_id", "scan_corner_edge_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_corner_edge_artifact_corner_edge_run_id", "scan_corner_edge_artifact", ["corner_edge_run_id"], unique=False)
    op.create_index("ix_scan_corner_edge_artifact_artifact_type", "scan_corner_edge_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_corner_edge_artifact_storage_backend", "scan_corner_edge_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_corner_edge_artifact_artifact_checksum", "scan_corner_edge_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_corner_edge_art_owner_created", "scan_corner_edge_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_art_run_type", "scan_corner_edge_artifact", ["corner_edge_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_corner_edge_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("corner_edge_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corner_edge_run_id"], ["scan_corner_edge_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_corner_edge_issue_owner_user_id", "scan_corner_edge_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_corner_edge_issue_corner_edge_run_id", "scan_corner_edge_issue", ["corner_edge_run_id"], unique=False)
    op.create_index("ix_scan_corner_edge_issue_issue_type", "scan_corner_edge_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_corner_edge_issue_severity", "scan_corner_edge_issue", ["severity"], unique=False)
    op.create_index("ix_scan_corner_edge_issue_owner_created", "scan_corner_edge_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_issue_run_type", "scan_corner_edge_issue", ["corner_edge_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_corner_edge_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("corner_edge_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corner_edge_run_id"], ["scan_corner_edge_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_corner_edge_history_owner_user_id", "scan_corner_edge_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_corner_edge_history_corner_edge_run_id", "scan_corner_edge_history", ["corner_edge_run_id"], unique=False)
    op.create_index("ix_scan_corner_edge_history_event_type", "scan_corner_edge_history", ["event_type"], unique=False)
    op.create_index("ix_scan_corner_edge_history_event_checksum", "scan_corner_edge_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_corner_edge_hist_owner_created", "scan_corner_edge_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_corner_edge_hist_run_type", "scan_corner_edge_history", ["corner_edge_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_corner_edge_hist_run_type", table_name="scan_corner_edge_history")
    op.drop_index("ix_scan_corner_edge_hist_owner_created", table_name="scan_corner_edge_history")
    op.drop_index("ix_scan_corner_edge_history_event_checksum", table_name="scan_corner_edge_history")
    op.drop_index("ix_scan_corner_edge_history_event_type", table_name="scan_corner_edge_history")
    op.drop_index("ix_scan_corner_edge_history_corner_edge_run_id", table_name="scan_corner_edge_history")
    op.drop_index("ix_scan_corner_edge_history_owner_user_id", table_name="scan_corner_edge_history")
    op.drop_table("scan_corner_edge_history")

    op.drop_index("ix_scan_corner_edge_issue_run_type", table_name="scan_corner_edge_issue")
    op.drop_index("ix_scan_corner_edge_issue_owner_created", table_name="scan_corner_edge_issue")
    op.drop_index("ix_scan_corner_edge_issue_severity", table_name="scan_corner_edge_issue")
    op.drop_index("ix_scan_corner_edge_issue_issue_type", table_name="scan_corner_edge_issue")
    op.drop_index("ix_scan_corner_edge_issue_corner_edge_run_id", table_name="scan_corner_edge_issue")
    op.drop_index("ix_scan_corner_edge_issue_owner_user_id", table_name="scan_corner_edge_issue")
    op.drop_table("scan_corner_edge_issue")

    op.drop_index("ix_scan_corner_edge_art_run_type", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_art_owner_created", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_artifact_artifact_checksum", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_artifact_storage_backend", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_artifact_artifact_type", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_artifact_corner_edge_run_id", table_name="scan_corner_edge_artifact")
    op.drop_index("ix_scan_corner_edge_artifact_owner_user_id", table_name="scan_corner_edge_artifact")
    op.drop_table("scan_corner_edge_artifact")

    op.drop_index("ix_scan_corner_edge_evidence_run_conf", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_run_rank", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_owner_created", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_region_type", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_severity_hint", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_confidence_score", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_evidence_type", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_evidence_rank", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_defect_evidence_id", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_corner_edge_run_id", table_name="scan_corner_edge_evidence")
    op.drop_index("ix_scan_corner_edge_evidence_owner_user_id", table_name="scan_corner_edge_evidence")
    op.drop_table("scan_corner_edge_evidence")

    op.drop_index("ix_scan_corner_edge_run_defect", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_scan_image", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_owner_created", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_engine_version", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_detection_status", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_corner_edge_checksum", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_source_checksum", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_defect_run_id", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_scan_image_id", table_name="scan_corner_edge_run")
    op.drop_index("ix_scan_corner_edge_run_owner_user_id", table_name="scan_corner_edge_run")
    op.drop_table("scan_corner_edge_run")
