"""add scan visual evidence system

Revision ID: 20260609_0097
Revises: 20260608_0096
Create Date: 2026-06-09 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260609_0097"
down_revision = "20260608_0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_visual_evidence_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=False),
        sa.Column("aggregation_run_id", sa.Integer(), nullable=True),
        sa.Column("grading_assistance_run_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("visual_evidence_checksum", sa.String(length=64), nullable=False),
        sa.Column("evidence_status", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("input_manifest_json", sa.JSON(), nullable=False),
        sa.Column("output_manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["aggregation_run_id"], ["scan_defect_aggregation_run.id"]),
        sa.ForeignKeyConstraint(["grading_assistance_run_id"], ["scan_grading_assistance_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "visual_evidence_checksum", name="uq_scan_visual_evidence_run_owner_checksum"),
    )
    op.create_index("ix_scan_visual_evidence_run_owner_user_id", "scan_visual_evidence_run", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_scan_image_id", "scan_visual_evidence_run", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_aggregation_run_id", "scan_visual_evidence_run", ["aggregation_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_grading_assistance_run_id", "scan_visual_evidence_run", ["grading_assistance_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_source_checksum", "scan_visual_evidence_run", ["source_checksum"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_visual_evidence_checksum", "scan_visual_evidence_run", ["visual_evidence_checksum"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_evidence_status", "scan_visual_evidence_run", ["evidence_status"], unique=False)
    op.create_index("ix_scan_visual_evidence_run_engine_version", "scan_visual_evidence_run", ["engine_version"], unique=False)
    op.create_index("ix_scan_visual_ev_run_owner_created", "scan_visual_evidence_run", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_run_scan_image", "scan_visual_evidence_run", ["scan_image_id", "created_at", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_package",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("package_type", sa.String(length=40), nullable=False),
        sa.Column("package_status", sa.String(length=24), nullable=False),
        sa.Column("package_title", sa.String(length=255), nullable=False),
        sa.Column("package_summary", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_visual_evidence_package_owner_user_id", "scan_visual_evidence_package", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_package_visual_evidence_run_id", "scan_visual_evidence_package", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_package_package_type", "scan_visual_evidence_package", ["package_type"], unique=False)
    op.create_index("ix_scan_visual_evidence_package_package_status", "scan_visual_evidence_package", ["package_status"], unique=False)
    op.create_index("ix_scan_visual_ev_pkg_owner_created", "scan_visual_evidence_package", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_pkg_run_type", "scan_visual_evidence_package", ["visual_evidence_run_id", "package_type", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("item_rank", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=48), nullable=False),
        sa.Column("item_title", sa.String(length=255), nullable=False),
        sa.Column("item_summary", sa.String(length=1024), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("severity_hint", sa.String(length=16), nullable=True),
        sa.Column("region_type", sa.String(length=40), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["package_id"], ["scan_visual_evidence_package.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_visual_evidence_item_owner_user_id", "scan_visual_evidence_item", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_item_visual_evidence_run_id", "scan_visual_evidence_item", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_item_package_id", "scan_visual_evidence_item", ["package_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_item_item_rank", "scan_visual_evidence_item", ["item_rank"], unique=False)
    op.create_index("ix_scan_visual_evidence_item_source_system", "scan_visual_evidence_item", ["source_system"], unique=False)
    op.create_index("ix_scan_visual_evidence_item_source_record_id", "scan_visual_evidence_item", ["source_record_id"], unique=False)
    op.create_index("ix_scan_visual_ev_item_owner_created", "scan_visual_evidence_item", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_item_run_pkg", "scan_visual_evidence_item", ["visual_evidence_run_id", "package_id", "item_rank", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_annotation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("annotation_type", sa.String(length=32), nullable=False),
        sa.Column("x_min", sa.Integer(), nullable=False),
        sa.Column("y_min", sa.Integer(), nullable=False),
        sa.Column("x_max", sa.Integer(), nullable=False),
        sa.Column("y_max", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("style_hint", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["scan_visual_evidence_item.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_visual_evidence_annotation_owner_user_id", "scan_visual_evidence_annotation", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_annotation_visual_evidence_run_id", "scan_visual_evidence_annotation", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_annotation_item_id", "scan_visual_evidence_annotation", ["item_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_annotation_annotation_type", "scan_visual_evidence_annotation", ["annotation_type"], unique=False)
    op.create_index("ix_scan_visual_evidence_annotation_display_order", "scan_visual_evidence_annotation", ["display_order"], unique=False)
    op.create_index("ix_scan_visual_ev_ann_owner_created", "scan_visual_evidence_annotation", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_ann_run_item", "scan_visual_evidence_annotation", ["visual_evidence_run_id", "item_id", "display_order", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("visual_evidence_run_id", "artifact_type", "artifact_checksum", name="uq_scan_visual_evidence_art_run_type_checksum"),
    )
    op.create_index("ix_scan_visual_evidence_artifact_owner_user_id", "scan_visual_evidence_artifact", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_artifact_visual_evidence_run_id", "scan_visual_evidence_artifact", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_artifact_artifact_type", "scan_visual_evidence_artifact", ["artifact_type"], unique=False)
    op.create_index("ix_scan_visual_evidence_artifact_artifact_checksum", "scan_visual_evidence_artifact", ["artifact_checksum"], unique=False)
    op.create_index("ix_scan_visual_ev_art_owner_created", "scan_visual_evidence_artifact", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_art_run_type", "scan_visual_evidence_artifact", ["visual_evidence_run_id", "artifact_type", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_visual_evidence_issue_owner_user_id", "scan_visual_evidence_issue", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_issue_visual_evidence_run_id", "scan_visual_evidence_issue", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_issue_issue_type", "scan_visual_evidence_issue", ["issue_type"], unique=False)
    op.create_index("ix_scan_visual_evidence_issue_severity", "scan_visual_evidence_issue", ["severity"], unique=False)
    op.create_index("ix_scan_visual_ev_issue_owner_created", "scan_visual_evidence_issue", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_issue_run_type", "scan_visual_evidence_issue", ["visual_evidence_run_id", "issue_type", "id"], unique=False)

    op.create_table(
        "scan_visual_evidence_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("visual_evidence_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["visual_evidence_run_id"], ["scan_visual_evidence_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_visual_evidence_history_owner_user_id", "scan_visual_evidence_history", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_history_visual_evidence_run_id", "scan_visual_evidence_history", ["visual_evidence_run_id"], unique=False)
    op.create_index("ix_scan_visual_evidence_history_event_type", "scan_visual_evidence_history", ["event_type"], unique=False)
    op.create_index("ix_scan_visual_evidence_history_event_checksum", "scan_visual_evidence_history", ["event_checksum"], unique=False)
    op.create_index("ix_scan_visual_ev_hist_owner_created", "scan_visual_evidence_history", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_visual_ev_hist_run_type", "scan_visual_evidence_history", ["visual_evidence_run_id", "event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_table("scan_visual_evidence_history")
    op.drop_table("scan_visual_evidence_issue")
    op.drop_table("scan_visual_evidence_artifact")
    op.drop_table("scan_visual_evidence_annotation")
    op.drop_table("scan_visual_evidence_item")
    op.drop_table("scan_visual_evidence_package")
    op.drop_table("scan_visual_evidence_run")
