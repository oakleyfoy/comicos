"""add scan reconciliation engine

Revision ID: 20260601_0089
Revises: 20260531_0088
Create Date: 2026-06-01 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260601_0089"
down_revision = "20260531_0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_reconciliation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("boundary_run_id", sa.Integer(), nullable=False),
        sa.Column("ocr_run_id", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_checksum", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=40), nullable=False),
        sa.Column("reconciliation_engine_version", sa.String(length=40), nullable=False),
        sa.Column("canonical_dataset_version", sa.String(length=64), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["boundary_run_id"], ["scan_boundary_run.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["scan_normalization_run.id"]),
        sa.ForeignKeyConstraint(["ocr_run_id"], ["scan_ocr_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "reconciliation_checksum", name="uq_scan_recon_run_owner_checksum"),
    )
    op.create_index("ix_scan_reconciliation_run_owner_user_id", "scan_reconciliation_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_run_scan_image_id", "scan_reconciliation_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_reconciliation_run_normalization_run_id", "scan_reconciliation_run", ["normalization_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_run_boundary_run_id", "scan_reconciliation_run", ["boundary_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_run_ocr_run_id", "scan_reconciliation_run", ["ocr_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_run_source_checksum", "scan_reconciliation_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_reconciliation_run_reconciliation_checksum", "scan_reconciliation_run", ["reconciliation_checksum"], unique=False)
    op.create_index("ix_scan_reconciliation_run_reconciliation_status", "scan_reconciliation_run", ["reconciliation_status"], unique=False)
    op.create_index("ix_scan_reconciliation_run_reconciliation_engine_version", "scan_reconciliation_run", ["reconciliation_engine_version"], unique=False)
    op.create_index("ix_scan_reconciliation_run_canonical_dataset_version", "scan_reconciliation_run", ["canonical_dataset_version"], unique=False)
    op.create_index("ix_scan_recon_run_owner_created", "scan_reconciliation_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_run_owner_status", "scan_reconciliation_run", ["owner_user_id", "reconciliation_status", "id"], unique=False)
    op.create_index("ix_scan_recon_run_scan_image", "scan_reconciliation_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_run_ocr_run", "scan_reconciliation_run", ["ocr_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_reconciliation_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=False),
        sa.Column("candidate_rank", sa.Integer(), nullable=False),
        sa.Column("canonical_comic_id", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("series_title", sa.String(length=255), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("variant_description", sa.String(length=255), nullable=True),
        sa.Column("publication_date", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("title_similarity_score", sa.Float(), nullable=False),
        sa.Column("issue_similarity_score", sa.Float(), nullable=False),
        sa.Column("publisher_similarity_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_comic_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_reconciliation_candidate_owner_user_id", "scan_reconciliation_candidate", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_candidate_reconciliation_run_id", "scan_reconciliation_candidate", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_candidate_candidate_rank", "scan_reconciliation_candidate", ["candidate_rank"], unique=False)
    op.create_index("ix_scan_reconciliation_candidate_canonical_comic_id", "scan_reconciliation_candidate", ["canonical_comic_id"], unique=False)
    op.create_index("ix_scan_reconciliation_candidate_confidence_score", "scan_reconciliation_candidate", ["confidence_score"], unique=False)
    op.create_index("ix_scan_recon_candidate_owner_created", "scan_reconciliation_candidate", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_candidate_run_rank", "scan_reconciliation_candidate", ["reconciliation_run_id", "candidate_rank", "id"], unique=False)
    op.create_index("ix_scan_recon_candidate_run_conf", "scan_reconciliation_candidate", ["reconciliation_run_id", "confidence_score", "id"], unique=False)

    op.create_table(
        "scan_reconciliation_decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=False),
        sa.Column("selected_candidate_id", sa.Integer(), nullable=True),
        sa.Column("decision_status", sa.String(length=40), nullable=False),
        sa.Column("final_confidence_score", sa.Float(), nullable=False),
        sa.Column("decision_reason", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["selected_candidate_id"], ["scan_reconciliation_candidate.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_reconciliation_decision_owner_user_id", "scan_reconciliation_decision", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_decision_reconciliation_run_id", "scan_reconciliation_decision", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_decision_selected_candidate_id", "scan_reconciliation_decision", ["selected_candidate_id"], unique=False)
    op.create_index("ix_scan_reconciliation_decision_decision_status", "scan_reconciliation_decision", ["decision_status"], unique=False)
    op.create_index("ix_scan_reconciliation_decision_final_confidence_score", "scan_reconciliation_decision", ["final_confidence_score"], unique=False)
    op.create_index("ix_scan_recon_decision_owner_created", "scan_reconciliation_decision", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_decision_run", "scan_reconciliation_decision", ["reconciliation_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_reconciliation_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reconciliation_run_id", "artifact_type", "artifact_checksum", name="uq_scan_recon_art_run_type_checksum"),
    )
    op.create_index("ix_scan_reconciliation_artifact_owner_user_id", "scan_reconciliation_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_artifact_reconciliation_run_id", "scan_reconciliation_artifact", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_artifact_artifact_type", "scan_reconciliation_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_reconciliation_artifact_storage_backend", "scan_reconciliation_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_reconciliation_artifact_artifact_checksum", "scan_reconciliation_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_recon_art_owner_created", "scan_reconciliation_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_art_run_type", "scan_reconciliation_artifact", ["reconciliation_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_reconciliation_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_reconciliation_issue_owner_user_id", "scan_reconciliation_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_issue_reconciliation_run_id", "scan_reconciliation_issue", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_issue_issue_type", "scan_reconciliation_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_reconciliation_issue_severity", "scan_reconciliation_issue", ["severity"], unique=False)
    op.create_index("ix_scan_recon_issue_owner_created", "scan_reconciliation_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_issue_run_type", "scan_reconciliation_issue", ["reconciliation_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_reconciliation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_reconciliation_history_owner_user_id", "scan_reconciliation_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_reconciliation_history_reconciliation_run_id", "scan_reconciliation_history", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_reconciliation_history_event_type", "scan_reconciliation_history", ["event_type"], unique=False)
    op.create_index("ix_scan_reconciliation_history_event_checksum", "scan_reconciliation_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_recon_hist_owner_created", "scan_reconciliation_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_recon_hist_run_type", "scan_reconciliation_history", ["reconciliation_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_recon_hist_run_type", table_name="scan_reconciliation_history")
    op.drop_index("ix_scan_recon_hist_owner_created", table_name="scan_reconciliation_history")
    op.drop_index("ix_scan_reconciliation_history_event_checksum", table_name="scan_reconciliation_history")
    op.drop_index("ix_scan_reconciliation_history_event_type", table_name="scan_reconciliation_history")
    op.drop_index("ix_scan_reconciliation_history_reconciliation_run_id", table_name="scan_reconciliation_history")
    op.drop_index("ix_scan_reconciliation_history_owner_user_id", table_name="scan_reconciliation_history")
    op.drop_table("scan_reconciliation_history")

    op.drop_index("ix_scan_recon_issue_run_type", table_name="scan_reconciliation_issue")
    op.drop_index("ix_scan_recon_issue_owner_created", table_name="scan_reconciliation_issue")
    op.drop_index("ix_scan_reconciliation_issue_severity", table_name="scan_reconciliation_issue")
    op.drop_index("ix_scan_reconciliation_issue_issue_type", table_name="scan_reconciliation_issue")
    op.drop_index("ix_scan_reconciliation_issue_reconciliation_run_id", table_name="scan_reconciliation_issue")
    op.drop_index("ix_scan_reconciliation_issue_owner_user_id", table_name="scan_reconciliation_issue")
    op.drop_table("scan_reconciliation_issue")

    op.drop_index("ix_scan_recon_art_run_type", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_recon_art_owner_created", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_reconciliation_artifact_artifact_checksum", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_reconciliation_artifact_storage_backend", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_reconciliation_artifact_artifact_type", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_reconciliation_artifact_reconciliation_run_id", table_name="scan_reconciliation_artifact")
    op.drop_index("ix_scan_reconciliation_artifact_owner_user_id", table_name="scan_reconciliation_artifact")
    op.drop_table("scan_reconciliation_artifact")

    op.drop_index("ix_scan_recon_decision_run", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_recon_decision_owner_created", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_reconciliation_decision_final_confidence_score", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_reconciliation_decision_decision_status", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_reconciliation_decision_selected_candidate_id", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_reconciliation_decision_reconciliation_run_id", table_name="scan_reconciliation_decision")
    op.drop_index("ix_scan_reconciliation_decision_owner_user_id", table_name="scan_reconciliation_decision")
    op.drop_table("scan_reconciliation_decision")

    op.drop_index("ix_scan_recon_candidate_run_conf", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_recon_candidate_run_rank", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_recon_candidate_owner_created", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_reconciliation_candidate_confidence_score", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_reconciliation_candidate_canonical_comic_id", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_reconciliation_candidate_candidate_rank", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_reconciliation_candidate_reconciliation_run_id", table_name="scan_reconciliation_candidate")
    op.drop_index("ix_scan_reconciliation_candidate_owner_user_id", table_name="scan_reconciliation_candidate")
    op.drop_table("scan_reconciliation_candidate")

    op.drop_index("ix_scan_recon_run_ocr_run", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_recon_run_scan_image", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_recon_run_owner_status", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_recon_run_owner_created", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_canonical_dataset_version", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_reconciliation_engine_version", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_reconciliation_status", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_reconciliation_checksum", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_source_checksum", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_ocr_run_id", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_boundary_run_id", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_normalization_run_id", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_scan_image_id", table_name="scan_reconciliation_run")
    op.drop_index("ix_scan_reconciliation_run_owner_user_id", table_name="scan_reconciliation_run")
    op.drop_table("scan_reconciliation_run")
