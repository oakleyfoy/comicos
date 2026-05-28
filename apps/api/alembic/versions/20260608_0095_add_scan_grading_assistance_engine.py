"""add scan grading assistance engine

Revision ID: 20260608_0096
Revises: 20260607_0095
Create Date: 2026-06-08 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0096"
down_revision = "20260607_0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_grading_assistance_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("grading_assistance_checksum", sa.String(length=64), nullable=False),
        sa.Column("assistance_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["scan_reconciliation_run.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "grading_assistance_checksum", name="uq_scan_grading_assist_run_owner_checksum"),
    )
    op.create_index("ix_scan_grading_assistance_run_owner_user_id", "scan_grading_assistance_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_scan_image_id", "scan_grading_assistance_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_aggregation_run_id", "scan_grading_assistance_run", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_reconciliation_run_id", "scan_grading_assistance_run", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_source_checksum", "scan_grading_assistance_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_grading_assistance_checksum", "scan_grading_assistance_run", ["grading_assistance_checksum"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_assistance_status", "scan_grading_assistance_run", ["assistance_status"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_engine_version", "scan_grading_assistance_run", ["engine_version"], unique=False)
    op.create_index("ix_scan_grading_assistance_run_rubric_version", "scan_grading_assistance_run", ["rubric_version"], unique=False)
    op.create_index("ix_scan_grading_assist_run_owner_created", "scan_grading_assistance_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_run_scan_image", "scan_grading_assistance_run", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_run_aggregation", "scan_grading_assistance_run", ["aggregation_run_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_grading_assistance_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=False),
        sa.Column("category_type", sa.String(length=32), nullable=False),
        sa.Column("category_status", sa.String(length=24), nullable=False),
        sa.Column("suggested_range_low", sa.Float(), nullable=False),
        sa.Column("suggested_range_high", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.String(length=1024), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_grading_assistance_category_owner_user_id", "scan_grading_assistance_category", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_category_grading_assistance_run_id", "scan_grading_assistance_category", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_category_category_type", "scan_grading_assistance_category", ["category_type"], unique=False)
    op.create_index("ix_scan_grading_assistance_category_category_status", "scan_grading_assistance_category", ["category_status"], unique=False)
    op.create_index("ix_scan_grading_assistance_category_confidence_score", "scan_grading_assistance_category", ["confidence_score"], unique=False)
    op.create_index("ix_scan_grading_assist_cat_owner_created", "scan_grading_assistance_category", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_cat_run_type", "scan_grading_assistance_category", ["grading_assistance_run_id", "category_type", "id"], unique=False)

    op.create_table(
        "scan_grading_assistance_finding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("source_cluster_id", sa.Integer(), nullable=True),
        sa.Column("source_detector", sa.String(length=40), nullable=False),
        sa.Column("finding_type", sa.String(length=48), nullable=False),
        sa.Column("finding_severity_hint", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("grade_pressure_hint", sa.String(length=16), nullable=False),
        sa.Column("finding_text", sa.String(length=1024), nullable=False),
        sa.Column("measurement_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["scan_grading_assistance_category.id"]),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_cluster_id"], ["scan_defect_aggregate_cluster.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_grading_assistance_finding_owner_user_id", "scan_grading_assistance_finding", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_grading_assistance_run_id", "scan_grading_assistance_finding", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_category_id", "scan_grading_assistance_finding", ["category_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_source_cluster_id", "scan_grading_assistance_finding", ["source_cluster_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_source_detector", "scan_grading_assistance_finding", ["source_detector"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_finding_type", "scan_grading_assistance_finding", ["finding_type"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_finding_severity_hint", "scan_grading_assistance_finding", ["finding_severity_hint"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_confidence_score", "scan_grading_assistance_finding", ["confidence_score"], unique=False)
    op.create_index("ix_scan_grading_assistance_finding_grade_pressure_hint", "scan_grading_assistance_finding", ["grade_pressure_hint"], unique=False)
    op.create_index("ix_scan_grading_assist_find_owner_created", "scan_grading_assistance_finding", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_find_run_cat", "scan_grading_assistance_finding", ["grading_assistance_run_id", "category_id", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_find_run_pressure", "scan_grading_assistance_finding", ["grading_assistance_run_id", "grade_pressure_hint", "id"], unique=False)

    op.create_table(
        "scan_grading_assistance_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grading_assistance_run_id", "artifact_type", "artifact_checksum", name="uq_scan_grading_assist_art_run_type_checksum"),
    )
    op.create_index("ix_scan_grading_assistance_artifact_owner_user_id", "scan_grading_assistance_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_artifact_grading_assistance_run_id", "scan_grading_assistance_artifact", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_artifact_artifact_type", "scan_grading_assistance_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_grading_assistance_artifact_storage_backend", "scan_grading_assistance_artifact", ["storage_backend"], unique=False)
    op.create_index("ix_scan_grading_assistance_artifact_artifact_checksum", "scan_grading_assistance_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_grading_assist_art_owner_created", "scan_grading_assistance_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_art_run_type", "scan_grading_assistance_artifact", ["grading_assistance_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_grading_assistance_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_grading_assistance_issue_owner_user_id", "scan_grading_assistance_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_issue_grading_assistance_run_id", "scan_grading_assistance_issue", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_issue_issue_type", "scan_grading_assistance_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_grading_assistance_issue_severity", "scan_grading_assistance_issue", ["severity"], unique=False)
    op.create_index("ix_scan_grading_assist_issue_owner_created", "scan_grading_assistance_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_issue_run_type", "scan_grading_assistance_issue", ["grading_assistance_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_grading_assistance_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_grading_assistance_history_owner_user_id", "scan_grading_assistance_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_history_grading_assistance_run_id", "scan_grading_assistance_history", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_grading_assistance_history_event_type", "scan_grading_assistance_history", ["event_type"], unique=False)
    op.create_index("ix_scan_grading_assistance_history_event_checksum", "scan_grading_assistance_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_grading_assist_hist_owner_created", "scan_grading_assistance_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_grading_assist_hist_run_type", "scan_grading_assistance_history", ["grading_assistance_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_grading_assist_hist_run_type", table_name="scan_grading_assistance_history")
    op.drop_index("ix_scan_grading_assist_hist_owner_created", table_name="scan_grading_assistance_history")
    op.drop_index("ix_scan_grading_assistance_history_event_checksum", table_name="scan_grading_assistance_history")
    op.drop_index("ix_scan_grading_assistance_history_event_type", table_name="scan_grading_assistance_history")
    op.drop_index("ix_scan_grading_assistance_history_grading_assistance_run_id", table_name="scan_grading_assistance_history")
    op.drop_index("ix_scan_grading_assistance_history_owner_user_id", table_name="scan_grading_assistance_history")
    op.drop_table("scan_grading_assistance_history")

    op.drop_index("ix_scan_grading_assist_issue_run_type", table_name="scan_grading_assistance_issue")
    op.drop_index("ix_scan_grading_assist_issue_owner_created", table_name="scan_grading_assistance_issue")
    op.drop_index("ix_scan_grading_assistance_issue_severity", table_name="scan_grading_assistance_issue")
    op.drop_index("ix_scan_grading_assistance_issue_issue_type", table_name="scan_grading_assistance_issue")
    op.drop_index("ix_scan_grading_assistance_issue_grading_assistance_run_id", table_name="scan_grading_assistance_issue")
    op.drop_index("ix_scan_grading_assistance_issue_owner_user_id", table_name="scan_grading_assistance_issue")
    op.drop_table("scan_grading_assistance_issue")

    op.drop_index("ix_scan_grading_assist_art_run_type", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assist_art_owner_created", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assistance_artifact_artifact_checksum", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assistance_artifact_storage_backend", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assistance_artifact_artifact_type", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assistance_artifact_grading_assistance_run_id", table_name="scan_grading_assistance_artifact")
    op.drop_index("ix_scan_grading_assistance_artifact_owner_user_id", table_name="scan_grading_assistance_artifact")
    op.drop_table("scan_grading_assistance_artifact")

    op.drop_index("ix_scan_grading_assist_find_run_pressure", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assist_find_run_cat", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assist_find_owner_created", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_grade_pressure_hint", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_confidence_score", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_finding_severity_hint", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_finding_type", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_source_detector", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_source_cluster_id", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_category_id", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_grading_assistance_run_id", table_name="scan_grading_assistance_finding")
    op.drop_index("ix_scan_grading_assistance_finding_owner_user_id", table_name="scan_grading_assistance_finding")
    op.drop_table("scan_grading_assistance_finding")

    op.drop_index("ix_scan_grading_assist_cat_run_type", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assist_cat_owner_created", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assistance_category_confidence_score", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assistance_category_category_status", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assistance_category_category_type", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assistance_category_grading_assistance_run_id", table_name="scan_grading_assistance_category")
    op.drop_index("ix_scan_grading_assistance_category_owner_user_id", table_name="scan_grading_assistance_category")
    op.drop_table("scan_grading_assistance_category")

    op.drop_index("ix_scan_grading_assist_run_aggregation", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assist_run_scan_image", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assist_run_owner_created", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_rubric_version", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_engine_version", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_assistance_status", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_grading_assistance_checksum", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_source_checksum", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_reconciliation_run_id", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_aggregation_run_id", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_scan_image_id", table_name="scan_grading_assistance_run")
    op.drop_index("ix_scan_grading_assistance_run_owner_user_id", table_name="scan_grading_assistance_run")
    op.drop_table("scan_grading_assistance_run")
