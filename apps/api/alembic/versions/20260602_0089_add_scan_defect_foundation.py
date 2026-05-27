"""add scan defect foundation

Revision ID: 20260602_0090
Revises: 20260601_0089
Create Date: 2026-06-02 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260602_0090"
down_revision = "20260601_0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_defect_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=True),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("source_artifact_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("defect_checksum", sa.String(length=64), nullable=False),
        sa.Column("defect_status", sa.String(length=40), nullable=False),
        sa.Column("detection_engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["scan_normalization_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "defect_checksum", name="uq_scan_defect_run_owner_checksum"),
    )
    op.create_index("ix_scan_defect_run_owner_user_id", "scan_defect_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_run_scan_image_id", "scan_defect_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_defect_run_normalization_run_id", "scan_defect_run", ["normalization_run_id"], unique=False)
    op.create_index("ix_scan_defect_run_boundary_run_id", "scan_defect_run", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_defect_run_ocr_run_id", "scan_defect_run", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_defect_run_reconciliation_run_id", "scan_defect_run", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_defect_run_source_artifact_id", "scan_defect_run", ["source_artifact_id"], unique=False)
    op.create_index("ix_scan_defect_run_source_checksum", "scan_defect_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_defect_run_defect_checksum", "scan_defect_run", ["defect_checksum"], unique=False)
    op.create_index("ix_scan_defect_run_defect_status", "scan_defect_run", ["defect_status"], unique=False)
    op.create_index("ix_scan_defect_run_detection_engine_version", "scan_defect_run", ["detection_engine_version"], unique=False)
    op.create_index("ix_scan_defect_run_owner_created", "scan_defect_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_run_owner_status", "scan_defect_run", ["owner_user_id", "defect_status", "id"], unique=False)
    op.create_index("ix_scan_defect_run_scan_image", "scan_defect_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_run_boundary", "scan_defect_run", ["boundary_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_defect_region",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("region_type", sa.String(length=40), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("region_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("defect_run_id", "region_type", "region_checksum", name="uq_scan_defect_region_run_type_checksum"),
    )
    op.create_index("ix_scan_defect_region_owner_user_id", "scan_defect_region", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_region_defect_run_id", "scan_defect_region", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_defect_region_region_type", "scan_defect_region", ["region_type"], unique=False)
    op.create_index("ix_scan_defect_region_region_checksum", "scan_defect_region", ["region_checksum"], unique=False)
    op.create_index("ix_scan_defect_region_owner_created", "scan_defect_region", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_region_run_type", "scan_defect_region", ["defect_run_id", "region_type", "id"], unique=False)

    op.create_table(
        "scan_defect_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_category", sa.String(length=40), nullable=False),
        sa.Column("severity_hint", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["region_id"], ["scan_defect_region.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_evidence_owner_user_id", "scan_defect_evidence", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_evidence_defect_run_id", "scan_defect_evidence", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_defect_evidence_region_id", "scan_defect_evidence", ["region_id"], unique=False)
    op.create_index("ix_scan_defect_evidence_evidence_type", "scan_defect_evidence", ["evidence_type"], unique=False)
    op.create_index("ix_scan_defect_evidence_evidence_category", "scan_defect_evidence", ["evidence_category"], unique=False)
    op.create_index("ix_scan_defect_evidence_severity_hint", "scan_defect_evidence", ["severity_hint"], unique=False)
    op.create_index("ix_scan_defect_evidence_confidence_score", "scan_defect_evidence", ["confidence_score"], unique=False)
    op.create_index("ix_scan_defect_evidence_owner_created", "scan_defect_evidence", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_evidence_run_region", "scan_defect_evidence", ["defect_run_id", "region_id", "id"], unique=False)
    op.create_index("ix_scan_defect_evidence_run_conf", "scan_defect_evidence", ["defect_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_defect_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("defect_run_id", "artifact_type", "artifact_checksum", name="uq_scan_defect_art_run_type_checksum"),
    )
    op.create_index("ix_scan_defect_artifact_owner_user_id", "scan_defect_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_artifact_defect_run_id", "scan_defect_artifact", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_defect_artifact_artifact_type", "scan_defect_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_defect_artifact_storage_backend", "scan_defect_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_defect_artifact_artifact_checksum", "scan_defect_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_defect_artifact_owner_created", "scan_defect_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_artifact_run_type", "scan_defect_artifact", ["defect_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_defect_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_issue_owner_user_id", "scan_defect_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_issue_defect_run_id", "scan_defect_issue", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_defect_issue_issue_type", "scan_defect_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_defect_issue_severity", "scan_defect_issue", ["severity"], unique=False)
    op.create_index("ix_scan_defect_issue_owner_created", "scan_defect_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_issue_run_type", "scan_defect_issue", ["defect_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_defect_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("defect_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["defect_run_id"], ["scan_defect_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_defect_history_owner_user_id", "scan_defect_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_defect_history_defect_run_id", "scan_defect_history", ["defect_run_id"], unique=False)
    op.create_index("ix_scan_defect_history_event_type", "scan_defect_history", ["event_type"], unique=False)
    op.create_index("ix_scan_defect_history_event_checksum", "scan_defect_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_defect_history_owner_created", "scan_defect_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_defect_history_run_type", "scan_defect_history", ["defect_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_defect_history_run_type", table_name="scan_defect_history")
    op.drop_index("ix_scan_defect_history_owner_created", table_name="scan_defect_history")
    op.drop_index("ix_scan_defect_history_event_checksum", table_name="scan_defect_history")
    op.drop_index("ix_scan_defect_history_event_type", table_name="scan_defect_history")
    op.drop_index("ix_scan_defect_history_defect_run_id", table_name="scan_defect_history")
    op.drop_index("ix_scan_defect_history_owner_user_id", table_name="scan_defect_history")
    op.drop_table("scan_defect_history")

    op.drop_index("ix_scan_defect_issue_run_type", table_name="scan_defect_issue")
    op.drop_index("ix_scan_defect_issue_owner_created", table_name="scan_defect_issue")
    op.drop_index("ix_scan_defect_issue_severity", table_name="scan_defect_issue")
    op.drop_index("ix_scan_defect_issue_issue_type", table_name="scan_defect_issue")
    op.drop_index("ix_scan_defect_issue_defect_run_id", table_name="scan_defect_issue")
    op.drop_index("ix_scan_defect_issue_owner_user_id", table_name="scan_defect_issue")
    op.drop_table("scan_defect_issue")

    op.drop_index("ix_scan_defect_artifact_run_type", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_owner_created", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_artifact_checksum", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_storage_backend", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_artifact_type", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_defect_run_id", table_name="scan_defect_artifact")
    op.drop_index("ix_scan_defect_artifact_owner_user_id", table_name="scan_defect_artifact")
    op.drop_table("scan_defect_artifact")

    op.drop_index("ix_scan_defect_evidence_run_conf", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_run_region", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_owner_created", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_confidence_score", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_severity_hint", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_evidence_category", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_evidence_type", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_region_id", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_defect_run_id", table_name="scan_defect_evidence")
    op.drop_index("ix_scan_defect_evidence_owner_user_id", table_name="scan_defect_evidence")
    op.drop_table("scan_defect_evidence")

    op.drop_index("ix_scan_defect_region_run_type", table_name="scan_defect_region")
    op.drop_index("ix_scan_defect_region_owner_created", table_name="scan_defect_region")
    op.drop_index("ix_scan_defect_region_region_checksum", table_name="scan_defect_region")
    op.drop_index("ix_scan_defect_region_region_type", table_name="scan_defect_region")
    op.drop_index("ix_scan_defect_region_defect_run_id", table_name="scan_defect_region")
    op.drop_index("ix_scan_defect_region_owner_user_id", table_name="scan_defect_region")
    op.drop_table("scan_defect_region")

    op.drop_index("ix_scan_defect_run_boundary", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_scan_image", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_owner_status", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_owner_created", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_detection_engine_version", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_defect_status", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_defect_checksum", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_source_checksum", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_source_artifact_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_reconciliation_run_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_ocr_run_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_boundary_run_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_normalization_run_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_scan_image_id", table_name="scan_defect_run")
    op.drop_index("ix_scan_defect_run_owner_user_id", table_name="scan_defect_run")
    op.drop_table("scan_defect_run")
