"""add scan normalization engine

Revision ID: 20260529_0086
Revises: 20260528_0085
Create Date: 2026-05-29 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260529_0086"
down_revision = "20260528_0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_normalization_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("source_sha256_checksum", sa.String(length=64), nullable=False),
        sa.Column("normalization_checksum", sa.String(length=64), nullable=False),
        sa.Column("normalization_status", sa.String(length=24), nullable=False),
        sa.Column("orientation_code", sa.String(length=24), nullable=False),
        sa.Column("rotation_degrees", sa.Integer(), nullable=False),
        sa.Column("crop_left", sa.Integer(), nullable=False),
        sa.Column("crop_top", sa.Integer(), nullable=False),
        sa.Column("crop_right", sa.Integer(), nullable=False),
        sa.Column("crop_bottom", sa.Integer(), nullable=False),
        sa.Column("perspective_strength", sa.Integer(), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("replayed_from_run_id", sa.Integer(), nullable=True),
        sa.Column("final_artifact_id", sa.Integer(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["replayed_from_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "normalization_checksum", name="uq_scan_norm_run_owner_checksum"),
    )
    op.create_index("ix_scan_normalization_run_owner_user_id", "scan_normalization_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_normalization_run_scan_image_id", "scan_normalization_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_normalization_run_source_sha256_checksum", "scan_normalization_run", ["source_sha256_checksum"], unique=False)
    op.create_index("ix_scan_normalization_run_normalization_checksum", "scan_normalization_run", ["normalization_checksum"], unique=False)
    op.create_index("ix_scan_normalization_run_normalization_status", "scan_normalization_run", ["normalization_status"], unique=False)
    op.create_index("ix_scan_normalization_run_orientation_code", "scan_normalization_run", ["orientation_code"], unique=False)
    op.create_index("ix_scan_normalization_run_replayed_from_run_id", "scan_normalization_run", ["replayed_from_run_id"], unique=False)
    op.create_index("ix_scan_normalization_run_final_artifact_id", "scan_normalization_run", ["final_artifact_id"], unique=False)
    op.create_index("ix_scan_norm_run_owner_created", "scan_normalization_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_norm_run_owner_status", "scan_normalization_run", ["owner_user_id", "normalization_status", "id"], unique=False)
    op.create_index("ix_scan_norm_run_scan_image", "scan_normalization_run", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_normalization_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("parent_artifact_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("artifact_order", sa.Integer(), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("dpi_x", sa.Integer(), nullable=True),
        sa.Column("dpi_y", sa.Integer(), nullable=True),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("parent_checksum", sa.String(length=64), nullable=True),
        sa.Column("normalization_status", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["parent_artifact_id"], ["scan_normalization_artifact.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["scan_normalization_run_id"], ["scan_normalization_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scan_normalization_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_norm_art_run_type_checksum",
        ),
    )
    op.create_index("ix_scan_normalization_artifact_scan_normalization_run_id", "scan_normalization_artifact", ["scan_normalization_run_id"], unique=False)
    op.create_index("ix_scan_normalization_artifact_owner_user_id", "scan_normalization_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_normalization_artifact_scan_image_id", "scan_normalization_artifact", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_normalization_artifact_parent_artifact_id", "scan_normalization_artifact", ["parent_artifact_id"], unique=False)
    op.create_index("ix_scan_normalization_artifact_artifact_type", "scan_normalization_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_normalization_artifact_storage_backend", "scan_normalization_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_normalization_artifact_artifact_checksum", "scan_normalization_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_normalization_artifact_parent_checksum", "scan_normalization_artifact", ["parent_checksum"], unique=False)
    op.create_index("ix_scan_normalization_artifact_normalization_status", "scan_normalization_artifact", ["normalization_status"], unique=False)
    op.create_index("ix_scan_norm_art_owner_created", "scan_normalization_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_norm_art_scan_image", "scan_normalization_artifact", ["scan_image_id", "artifact_order", "id"], unique=False)
    op.create_index("ix_scan_norm_art_status", "scan_normalization_artifact", ["normalization_status", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_normalization_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("normalization_status", sa.String(length=24), nullable=False),
        sa.Column("metric_value", sa.String(length=64), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["scan_normalization_run_id"], ["scan_normalization_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_normalization_issue_scan_normalization_run_id", "scan_normalization_issue", ["scan_normalization_run_id"], unique=False)
    op.create_index("ix_scan_normalization_issue_owner_user_id", "scan_normalization_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_normalization_issue_scan_image_id", "scan_normalization_issue", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_normalization_issue_issue_type", "scan_normalization_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_normalization_issue_severity", "scan_normalization_issue", ["severity"], unique=False)
    op.create_index("ix_scan_normalization_issue_normalization_status", "scan_normalization_issue", ["normalization_status"], unique=False)
    op.create_index("ix_scan_norm_issue_owner_created", "scan_normalization_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_norm_issue_scan_image", "scan_normalization_issue", ["scan_image_id", "issue_type", "id"], unique=False)
    op.create_index("ix_scan_norm_issue_status", "scan_normalization_issue", ["normalization_status", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_normalization_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("history_order", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_checksum", sa.String(length=64), nullable=True),
        sa.Column("to_checksum", sa.String(length=64), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["scan_normalization_run_id"], ["scan_normalization_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_normalization_history_scan_normalization_run_id", "scan_normalization_history", ["scan_normalization_run_id"], unique=False)
    op.create_index("ix_scan_normalization_history_owner_user_id", "scan_normalization_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_normalization_history_scan_image_id", "scan_normalization_history", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_normalization_history_stage_name", "scan_normalization_history", ["stage_name"], unique=False)
    op.create_index("ix_scan_normalization_history_event_type", "scan_normalization_history", ["event_type"], unique=False)
    op.create_index("ix_scan_normalization_history_from_checksum", "scan_normalization_history", ["from_checksum"], unique=False)
    op.create_index("ix_scan_normalization_history_to_checksum", "scan_normalization_history", ["to_checksum"], unique=False)
    op.create_index("ix_scan_norm_hist_owner_created", "scan_normalization_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_norm_hist_run_order", "scan_normalization_history", ["scan_normalization_run_id", "history_order", "id"], unique=False)
    op.create_index("ix_scan_norm_hist_scan_image", "scan_normalization_history", ["scan_image_id", "stage_name", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_norm_hist_scan_image", table_name="scan_normalization_history")
    op.drop_index("ix_scan_norm_hist_run_order", table_name="scan_normalization_history")
    op.drop_index("ix_scan_norm_hist_owner_created", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_to_checksum", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_from_checksum", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_event_type", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_stage_name", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_scan_image_id", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_owner_user_id", table_name="scan_normalization_history")
    op.drop_index("ix_scan_normalization_history_scan_normalization_run_id", table_name="scan_normalization_history")
    op.drop_table("scan_normalization_history")

    op.drop_index("ix_scan_norm_issue_status", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_norm_issue_scan_image", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_norm_issue_owner_created", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_normalization_status", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_severity", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_issue_type", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_scan_image_id", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_owner_user_id", table_name="scan_normalization_issue")
    op.drop_index("ix_scan_normalization_issue_scan_normalization_run_id", table_name="scan_normalization_issue")
    op.drop_table("scan_normalization_issue")

    op.drop_index("ix_scan_norm_art_status", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_norm_art_scan_image", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_norm_art_owner_created", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_normalization_status", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_parent_checksum", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_artifact_checksum", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_storage_backend", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_artifact_type", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_parent_artifact_id", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_scan_image_id", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_owner_user_id", table_name="scan_normalization_artifact")
    op.drop_index("ix_scan_normalization_artifact_scan_normalization_run_id", table_name="scan_normalization_artifact")
    op.drop_table("scan_normalization_artifact")

    op.drop_index("ix_scan_norm_run_scan_image", table_name="scan_normalization_run")
    op.drop_index("ix_scan_norm_run_owner_status", table_name="scan_normalization_run")
    op.drop_index("ix_scan_norm_run_owner_created", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_final_artifact_id", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_replayed_from_run_id", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_orientation_code", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_normalization_status", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_normalization_checksum", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_source_sha256_checksum", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_scan_image_id", table_name="scan_normalization_run")
    op.drop_index("ix_scan_normalization_run_owner_user_id", table_name="scan_normalization_run")
    op.drop_table("scan_normalization_run")
