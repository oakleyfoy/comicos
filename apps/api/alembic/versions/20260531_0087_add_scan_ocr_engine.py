"""add scan ocr engine

Revision ID: 20260531_0088
Revises: 20260530_0087
Create Date: 2026-05-31 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260531_0088"
down_revision = "20260530_0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_ocr_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("source_artifact_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("ocr_checksum", sa.String(length=64), nullable=False),
        sa.Column("ocr_status", sa.String(length=24), nullable=False),
        sa.Column("ocr_engine", sa.String(length=40), nullable=False),
        sa.Column("ocr_engine_version", sa.String(length=255), nullable=True),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["scan_normalization_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "ocr_checksum", name="uq_scan_ocr_run_owner_checksum"),
    )
    op.create_index("ix_scan_ocr_run_owner_user_id", "scan_ocr_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_run_scan_image_id", "scan_ocr_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_ocr_run_normalization_run_id", "scan_ocr_run", ["normalization_run_id"], unique=False)
    op.create_index("ix_scan_ocr_run_boundary_run_id", "scan_ocr_run", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_ocr_run_source_artifact_id", "scan_ocr_run", ["source_artifact_id"], unique=False)
    op.create_index("ix_scan_ocr_run_source_checksum", "scan_ocr_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_ocr_run_ocr_checksum", "scan_ocr_run", ["ocr_checksum"], unique=False)
    op.create_index("ix_scan_ocr_run_ocr_status", "scan_ocr_run", ["ocr_status"], unique=False)
    op.create_index("ix_scan_ocr_run_ocr_engine", "scan_ocr_run", ["ocr_engine"], unique=False)
    op.create_index("ix_scan_ocr_run_owner_created", "scan_ocr_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_run_owner_status", "scan_ocr_run", ["owner_user_id", "ocr_status", "id"], unique=False)
    op.create_index("ix_scan_ocr_run_scan_image", "scan_ocr_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_run_boundary", "scan_ocr_run", ["boundary_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_ocr_text_region",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("region_type", sa.String(length=40), nullable=False),
        sa.Column("extracted_text", sa.String(length=20000), nullable=False),
        sa.Column("normalized_text", sa.String(length=20000), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("rotation_angle", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_ocr_text_region_owner_user_id", "scan_ocr_text_region", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_text_region_ocr_run_id", "scan_ocr_text_region", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_ocr_text_region_region_type", "scan_ocr_text_region", ["region_type"], unique=False)
    op.create_index("ix_scan_ocr_text_region_confidence_score", "scan_ocr_text_region", ["confidence_score"], unique=False)
    op.create_index("ix_scan_ocr_region_owner_created", "scan_ocr_text_region", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_region_run_type", "scan_ocr_text_region", ["ocr_run_id", "region_type", "id"], unique=False)
    op.create_index("ix_scan_ocr_region_confidence", "scan_ocr_text_region", ["ocr_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_ocr_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("candidate_type", sa.String(length=32), nullable=False),
        sa.Column("candidate_value", sa.String(length=2000), nullable=False),
        sa.Column("normalized_candidate_value", sa.String(length=2000), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_region_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_region_id"], ["scan_ocr_text_region.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_ocr_candidate_owner_user_id", "scan_ocr_candidate", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_candidate_ocr_run_id", "scan_ocr_candidate", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_ocr_candidate_candidate_type", "scan_ocr_candidate", ["candidate_type"], unique=False)
    op.create_index("ix_scan_ocr_candidate_confidence_score", "scan_ocr_candidate", ["confidence_score"], unique=False)
    op.create_index("ix_scan_ocr_candidate_source_region_id", "scan_ocr_candidate", ["source_region_id"], unique=False)
    op.create_index("ix_scan_ocr_candidate_owner_created", "scan_ocr_candidate", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_candidate_run_type", "scan_ocr_candidate", ["ocr_run_id", "candidate_type", "id"], unique=False)
    op.create_index("ix_scan_ocr_candidate_confidence", "scan_ocr_candidate", ["ocr_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_ocr_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ocr_run_id", "artifact_type", "artifact_checksum", name="uq_scan_ocr_art_run_type_checksum"),
    )
    op.create_index("ix_scan_ocr_artifact_owner_user_id", "scan_ocr_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_artifact_ocr_run_id", "scan_ocr_artifact", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_ocr_artifact_artifact_type", "scan_ocr_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_ocr_artifact_artifact_checksum", "scan_ocr_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_ocr_artifact_owner_created", "scan_ocr_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_artifact_run_type", "scan_ocr_artifact", ["ocr_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_ocr_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_ocr_issue_owner_user_id", "scan_ocr_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_issue_ocr_run_id", "scan_ocr_issue", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_ocr_issue_issue_type", "scan_ocr_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_ocr_issue_severity", "scan_ocr_issue", ["severity"], unique=False)
    op.create_index("ix_scan_ocr_issue_owner_created", "scan_ocr_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_issue_run_type", "scan_ocr_issue", ["ocr_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_ocr_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_ocr_history_owner_user_id", "scan_ocr_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ocr_history_ocr_run_id", "scan_ocr_history", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_ocr_history_event_type", "scan_ocr_history", ["event_type"], unique=False)
    op.create_index("ix_scan_ocr_history_event_checksum", "scan_ocr_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_ocr_history_owner_created", "scan_ocr_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ocr_history_run_type", "scan_ocr_history", ["ocr_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_ocr_history_run_type", table_name="scan_ocr_history")
    op.drop_index("ix_scan_ocr_history_owner_created", table_name="scan_ocr_history")
    op.drop_index("ix_scan_ocr_history_event_checksum", table_name="scan_ocr_history")
    op.drop_index("ix_scan_ocr_history_event_type", table_name="scan_ocr_history")
    op.drop_index("ix_scan_ocr_history_ocr_run_id", table_name="scan_ocr_history")
    op.drop_index("ix_scan_ocr_history_owner_user_id", table_name="scan_ocr_history")
    op.drop_table("scan_ocr_history")

    op.drop_index("ix_scan_ocr_issue_run_type", table_name="scan_ocr_issue")
    op.drop_index("ix_scan_ocr_issue_owner_created", table_name="scan_ocr_issue")
    op.drop_index("ix_scan_ocr_issue_severity", table_name="scan_ocr_issue")
    op.drop_index("ix_scan_ocr_issue_issue_type", table_name="scan_ocr_issue")
    op.drop_index("ix_scan_ocr_issue_ocr_run_id", table_name="scan_ocr_issue")
    op.drop_index("ix_scan_ocr_issue_owner_user_id", table_name="scan_ocr_issue")
    op.drop_table("scan_ocr_issue")

    op.drop_index("ix_scan_ocr_artifact_run_type", table_name="scan_ocr_artifact")
    op.drop_index("ix_scan_ocr_artifact_owner_created", table_name="scan_ocr_artifact")
    op.drop_index("ix_scan_ocr_artifact_artifact_checksum", table_name="scan_ocr_artifact")
    op.drop_index("ix_scan_ocr_artifact_artifact_type", table_name="scan_ocr_artifact")
    op.drop_index("ix_scan_ocr_artifact_ocr_run_id", table_name="scan_ocr_artifact")
    op.drop_index("ix_scan_ocr_artifact_owner_user_id", table_name="scan_ocr_artifact")
    op.drop_table("scan_ocr_artifact")

    op.drop_index("ix_scan_ocr_candidate_confidence", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_run_type", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_owner_created", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_source_region_id", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_confidence_score", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_candidate_type", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_ocr_run_id", table_name="scan_ocr_candidate")
    op.drop_index("ix_scan_ocr_candidate_owner_user_id", table_name="scan_ocr_candidate")
    op.drop_table("scan_ocr_candidate")

    op.drop_index("ix_scan_ocr_region_confidence", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_region_run_type", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_region_owner_created", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_text_region_confidence_score", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_text_region_region_type", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_text_region_ocr_run_id", table_name="scan_ocr_text_region")
    op.drop_index("ix_scan_ocr_text_region_owner_user_id", table_name="scan_ocr_text_region")
    op.drop_table("scan_ocr_text_region")

    op.drop_index("ix_scan_ocr_run_boundary", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_scan_image", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_owner_status", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_owner_created", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_ocr_engine", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_ocr_status", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_ocr_checksum", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_source_checksum", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_source_artifact_id", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_boundary_run_id", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_normalization_run_id", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_scan_image_id", table_name="scan_ocr_run")
    op.drop_index("ix_scan_ocr_run_owner_user_id", table_name="scan_ocr_run")
    op.drop_table("scan_ocr_run")
