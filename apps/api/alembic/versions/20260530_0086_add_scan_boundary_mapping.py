"""add scan boundary mapping

Revision ID: 20260530_0087
Revises: 20260529_0086
Create Date: 2026-05-30 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260530_0087"
down_revision = "20260529_0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_boundary_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("source_artifact_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("boundary_checksum", sa.String(length=64), nullable=False),
        sa.Column("boundary_status", sa.String(length=24), nullable=False),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["scan_normalization_artifact.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "boundary_checksum", name="uq_scan_boundary_run_owner_checksum"),
    )
    op.create_index("ix_scan_boundary_run_owner_user_id", "scan_boundary_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_boundary_run_scan_image_id", "scan_boundary_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_boundary_run_normalization_run_id", "scan_boundary_run", ["normalization_run_id"], unique=False)
    op.create_index("ix_scan_boundary_run_source_artifact_id", "scan_boundary_run", ["source_artifact_id"], unique=False)
    op.create_index("ix_scan_boundary_run_source_checksum", "scan_boundary_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_boundary_run_boundary_checksum", "scan_boundary_run", ["boundary_checksum"], unique=False)
    op.create_index("ix_scan_boundary_run_boundary_status", "scan_boundary_run", ["boundary_status"], unique=False)
    op.create_index("ix_scan_boundary_run_algorithm_version", "scan_boundary_run", ["algorithm_version"], unique=False)
    op.create_index("ix_scan_boundary_run_owner_created", "scan_boundary_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_run_owner_status", "scan_boundary_run", ["owner_user_id", "boundary_status", "id"], unique=False)
    op.create_index("ix_scan_boundary_run_scan_image", "scan_boundary_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_run_norm_run", "scan_boundary_run", ["normalization_run_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_run_source_art", "scan_boundary_run", ["source_artifact_id", "id"], unique=False)

    op.create_table(
        "scan_boundary_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "boundary_run_id",
            "artifact_type",
            "artifact_checksum",
            name="uq_scan_boundary_art_run_type_checksum",
        ),
    )
    op.create_index("ix_scan_boundary_artifact_owner_user_id", "scan_boundary_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_boundary_artifact_boundary_run_id", "scan_boundary_artifact", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_boundary_artifact_scan_image_id", "scan_boundary_artifact", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_boundary_artifact_artifact_type", "scan_boundary_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_boundary_artifact_artifact_checksum", "scan_boundary_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_boundary_art_owner_created", "scan_boundary_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_art_scan_image", "scan_boundary_artifact", ["scan_image_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_boundary_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_boundary_issue_owner_user_id", "scan_boundary_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_boundary_issue_boundary_run_id", "scan_boundary_issue", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_boundary_issue_scan_image_id", "scan_boundary_issue", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_boundary_issue_issue_type", "scan_boundary_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_boundary_issue_severity", "scan_boundary_issue", ["severity"], unique=False)
    op.create_index("ix_scan_boundary_issue_owner_created", "scan_boundary_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_issue_scan_image", "scan_boundary_issue", ["scan_image_id", "issue_type", "id"], unique=False)
    op.create_index("ix_scan_boundary_issue_run", "scan_boundary_issue", ["boundary_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_boundary_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_boundary_history_owner_user_id", "scan_boundary_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_boundary_history_boundary_run_id", "scan_boundary_history", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_boundary_history_scan_image_id", "scan_boundary_history", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_boundary_history_event_type", "scan_boundary_history", ["event_type"], unique=False)
    op.create_index("ix_scan_boundary_history_event_checksum", "scan_boundary_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_boundary_hist_owner_created", "scan_boundary_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_hist_run", "scan_boundary_history", ["boundary_run_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_boundary_hist_scan_image", "scan_boundary_history", ["scan_image_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_boundary_hist_scan_image", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_hist_run", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_hist_owner_created", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_history_event_checksum", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_history_event_type", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_history_scan_image_id", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_history_boundary_run_id", table_name="scan_boundary_history")
    op.drop_index("ix_scan_boundary_history_owner_user_id", table_name="scan_boundary_history")
    op.drop_table("scan_boundary_history")

    op.drop_index("ix_scan_boundary_issue_run", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_scan_image", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_owner_created", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_severity", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_issue_type", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_scan_image_id", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_boundary_run_id", table_name="scan_boundary_issue")
    op.drop_index("ix_scan_boundary_issue_owner_user_id", table_name="scan_boundary_issue")
    op.drop_table("scan_boundary_issue")

    op.drop_index("ix_scan_boundary_art_scan_image", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_art_owner_created", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_artifact_artifact_checksum", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_artifact_artifact_type", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_artifact_scan_image_id", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_artifact_boundary_run_id", table_name="scan_boundary_artifact")
    op.drop_index("ix_scan_boundary_artifact_owner_user_id", table_name="scan_boundary_artifact")
    op.drop_table("scan_boundary_artifact")

    op.drop_index("ix_scan_boundary_run_source_art", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_norm_run", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_scan_image", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_owner_status", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_owner_created", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_algorithm_version", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_boundary_status", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_boundary_checksum", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_source_checksum", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_source_artifact_id", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_normalization_run_id", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_scan_image_id", table_name="scan_boundary_run")
    op.drop_index("ix_scan_boundary_run_owner_user_id", table_name="scan_boundary_run")
    op.drop_table("scan_boundary_run")
