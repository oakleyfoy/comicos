"""add scan spine tick engine

Revision ID: 20260603_0091
Revises: 20260602_0090
Create Date: 2026-06-03 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260603_0091"
down_revision = "20260602_0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_spine_tick_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("spine_tick_checksum", sa.String(length=64), nullable=False),
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
        sa.UniqueConstraint("owner_user_id", "spine_tick_checksum", name="uq_scan_spine_tick_run_owner_checksum"),
    )
    op.create_index("ix_scan_spine_tick_run_owner_user_id", "scan_spine_tick_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_spine_tick_run_scan_image_id", "scan_spine_tick_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_spine_tick_run_defect_run_id", "scan_spine_tick_run", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_spine_tick_run_source_checksum", "scan_spine_tick_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_spine_tick_run_spine_tick_checksum", "scan_spine_tick_run", ["spine_tick_checksum"], unique=False)
    op.create_index("ix_scan_spine_tick_run_detection_status", "scan_spine_tick_run", ["detection_status"], unique=False)
    op.create_index("ix_scan_spine_tick_run_engine_version", "scan_spine_tick_run", ["engine_version"], unique=False)
    op.create_index("ix_scan_spine_tick_run_owner_created", "scan_spine_tick_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_run_scan_image", "scan_spine_tick_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_run_defect", "scan_spine_tick_run", ["defect_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_spine_tick_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spine_tick_run_id", sa.Integer(), nullable=False),
        sa.Column("defect_evidence_id", sa.Integer(), nullable=True),
        sa.Column("tick_rank", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("severity_hint", sa.String(length=16), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("angle_degrees", sa.Float(), nullable=False),
        sa.Column("edge_distance_px", sa.Integer(), nullable=False),
        sa.Column("spine_overlap_ratio", sa.Float(), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_evidence_id"], ["scan_defect_evidence.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spine_tick_run_id"], ["scan_spine_tick_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_spine_tick_evidence_owner_user_id", "scan_spine_tick_evidence", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_spine_tick_run_id", "scan_spine_tick_evidence", ["spine_tick_run_id"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_defect_evidence_id", "scan_spine_tick_evidence", ["defect_evidence_id"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_tick_rank", "scan_spine_tick_evidence", ["tick_rank"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_confidence_score", "scan_spine_tick_evidence", ["confidence_score"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_severity_hint", "scan_spine_tick_evidence", ["severity_hint"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_owner_created", "scan_spine_tick_evidence", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_run_rank", "scan_spine_tick_evidence", ["spine_tick_run_id", "tick_rank", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_evidence_run_conf", "scan_spine_tick_evidence", ["spine_tick_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_spine_tick_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spine_tick_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spine_tick_run_id"], ["scan_spine_tick_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spine_tick_run_id", "artifact_type", "artifact_checksum", name="uq_scan_spine_tick_art_run_type_checksum"),
    )
    op.create_index("ix_scan_spine_tick_artifact_owner_user_id", "scan_spine_tick_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_spine_tick_artifact_spine_tick_run_id", "scan_spine_tick_artifact", ["spine_tick_run_id"], unique=False)
    op.create_index("ix_scan_spine_tick_artifact_artifact_type", "scan_spine_tick_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_spine_tick_artifact_storage_backend", "scan_spine_tick_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_spine_tick_artifact_artifact_checksum", "scan_spine_tick_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_spine_tick_art_owner_created", "scan_spine_tick_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_art_run_type", "scan_spine_tick_artifact", ["spine_tick_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_spine_tick_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spine_tick_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spine_tick_run_id"], ["scan_spine_tick_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_spine_tick_issue_owner_user_id", "scan_spine_tick_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_spine_tick_issue_spine_tick_run_id", "scan_spine_tick_issue", ["spine_tick_run_id"], unique=False)
    op.create_index("ix_scan_spine_tick_issue_issue_type", "scan_spine_tick_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_spine_tick_issue_severity", "scan_spine_tick_issue", ["severity"], unique=False)
    op.create_index("ix_scan_spine_tick_issue_owner_created", "scan_spine_tick_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_issue_run_type", "scan_spine_tick_issue", ["spine_tick_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_spine_tick_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spine_tick_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spine_tick_run_id"], ["scan_spine_tick_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_spine_tick_history_owner_user_id", "scan_spine_tick_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_spine_tick_history_spine_tick_run_id", "scan_spine_tick_history", ["spine_tick_run_id"], unique=False)
    op.create_index("ix_scan_spine_tick_history_event_type", "scan_spine_tick_history", ["event_type"], unique=False)
    op.create_index("ix_scan_spine_tick_history_event_checksum", "scan_spine_tick_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_spine_tick_hist_owner_created", "scan_spine_tick_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_spine_tick_hist_run_type", "scan_spine_tick_history", ["spine_tick_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_spine_tick_hist_run_type", table_name="scan_spine_tick_history")
    op.drop_index("ix_scan_spine_tick_hist_owner_created", table_name="scan_spine_tick_history")
    op.drop_index("ix_scan_spine_tick_history_event_checksum", table_name="scan_spine_tick_history")
    op.drop_index("ix_scan_spine_tick_history_event_type", table_name="scan_spine_tick_history")
    op.drop_index("ix_scan_spine_tick_history_spine_tick_run_id", table_name="scan_spine_tick_history")
    op.drop_index("ix_scan_spine_tick_history_owner_user_id", table_name="scan_spine_tick_history")
    op.drop_table("scan_spine_tick_history")

    op.drop_index("ix_scan_spine_tick_issue_run_type", table_name="scan_spine_tick_issue")
    op.drop_index("ix_scan_spine_tick_issue_owner_created", table_name="scan_spine_tick_issue")
    op.drop_index("ix_scan_spine_tick_issue_severity", table_name="scan_spine_tick_issue")
    op.drop_index("ix_scan_spine_tick_issue_issue_type", table_name="scan_spine_tick_issue")
    op.drop_index("ix_scan_spine_tick_issue_spine_tick_run_id", table_name="scan_spine_tick_issue")
    op.drop_index("ix_scan_spine_tick_issue_owner_user_id", table_name="scan_spine_tick_issue")
    op.drop_table("scan_spine_tick_issue")

    op.drop_index("ix_scan_spine_tick_art_run_type", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_art_owner_created", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_artifact_artifact_checksum", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_artifact_storage_backend", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_artifact_artifact_type", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_artifact_spine_tick_run_id", table_name="scan_spine_tick_artifact")
    op.drop_index("ix_scan_spine_tick_artifact_owner_user_id", table_name="scan_spine_tick_artifact")
    op.drop_table("scan_spine_tick_artifact")

    op.drop_index("ix_scan_spine_tick_evidence_run_conf", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_run_rank", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_owner_created", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_severity_hint", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_confidence_score", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_tick_rank", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_defect_evidence_id", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_spine_tick_run_id", table_name="scan_spine_tick_evidence")
    op.drop_index("ix_scan_spine_tick_evidence_owner_user_id", table_name="scan_spine_tick_evidence")
    op.drop_table("scan_spine_tick_evidence")

    op.drop_index("ix_scan_spine_tick_run_defect", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_scan_image", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_owner_created", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_engine_version", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_detection_status", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_spine_tick_checksum", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_source_checksum", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_defect_run_id", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_scan_image_id", table_name="scan_spine_tick_run")
    op.drop_index("ix_scan_spine_tick_run_owner_user_id", table_name="scan_spine_tick_run")
    op.drop_table("scan_spine_tick_run")
