"""add p97 historical catalog acquisition

Revision ID: 20260614_0301
Revises: 20260613_0300
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0301"
down_revision = "20260613_0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_import_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.JSON(), nullable=True),
        sa.Column("total_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_import_job_source", "catalog_import_job", ["source"])
    op.create_index("ix_catalog_import_job_status", "catalog_import_job", ["status"])

    op.create_table(
        "catalog_import_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("record_type", sa.String(length=64), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["catalog_import_job.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_import_error_job_id", "catalog_import_error", ["job_id"])

    op.create_table(
        "catalog_upc_conflict",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("normalized_upc", sa.String(length=64), nullable=False),
        sa.Column("existing_issue_id", sa.Integer(), nullable=True),
        sa.Column("existing_variant_id", sa.Integer(), nullable=True),
        sa.Column("incoming_issue_id", sa.Integer(), nullable=True),
        sa.Column("incoming_variant_id", sa.Integer(), nullable=True),
        sa.Column("existing_source", sa.String(length=64), nullable=True),
        sa.Column("incoming_source", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["existing_issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["incoming_issue_id"], ["catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_upc_conflict_normalized_upc", "catalog_upc_conflict", ["normalized_upc"])
    op.create_index("ix_catalog_upc_conflict_status", "catalog_upc_conflict", ["status"])

    op.create_table(
        "catalog_duplicate_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("primary_entity_id", sa.Integer(), nullable=False),
        sa.Column("duplicate_entity_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_duplicate_candidate_status", "catalog_duplicate_candidate", ["status"])

    op.create_table(
        "catalog_merge_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("survivor_id", sa.Integer(), nullable=False),
        sa.Column("merged_id", sa.Integer(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recognition_certification_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upc_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cover_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_recognition_ms", sa.Numeric(12, 2), nullable=True),
        sa.Column("recognition_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recognition_certification_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("expected_issue_id", sa.Integer(), nullable=True),
        sa.Column("expected_variant_id", sa.Integer(), nullable=True),
        sa.Column("test_upc", sa.String(length=64), nullable=True),
        sa.Column("test_image_path", sa.Text(), nullable=True),
        sa.Column("expected_label", sa.String(length=255), nullable=True),
        sa.Column("actual_issue_id", sa.Integer(), nullable=True),
        sa.Column("actual_variant_id", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("recognition_ms", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["recognition_certification_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recognition_gap",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("scan_session_id", sa.Integer(), nullable=True),
        sa.Column("scan_item_id", sa.Integer(), nullable=True),
        sa.Column("certification_run_id", sa.Integer(), nullable=True),
        sa.Column("certification_item_id", sa.Integer(), nullable=True),
        sa.Column("gap_type", sa.String(length=64), nullable=False),
        sa.Column("submitted_upc", sa.String(length=64), nullable=True),
        sa.Column("submitted_image_path", sa.Text(), nullable=True),
        sa.Column("submitted_ocr_text", sa.Text(), nullable=True),
        sa.Column("expected_label", sa.String(length=255), nullable=True),
        sa.Column("predicted_issue_id", sa.Integer(), nullable=True),
        sa.Column("predicted_variant_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_session_id"], ["inventory_scan_session.id"]),
        sa.ForeignKeyConstraint(["scan_item_id"], ["inventory_scan_item.id"]),
        sa.ForeignKeyConstraint(["certification_run_id"], ["recognition_certification_run.id"]),
        sa.ForeignKeyConstraint(["certification_item_id"], ["recognition_certification_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("catalog_image", sa.Column("download_error", sa.Text(), nullable=True))
    op.add_column("catalog_image", sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("catalog_image", sa.Column("content_type", sa.String(length=128), nullable=True))
    op.add_column("catalog_image", sa.Column("file_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalog_image", "file_size_bytes")
    op.drop_column("catalog_image", "content_type")
    op.drop_column("catalog_image", "downloaded_at")
    op.drop_column("catalog_image", "download_error")
    op.drop_table("recognition_gap")
    op.drop_table("recognition_certification_item")
    op.drop_table("recognition_certification_run")
    op.drop_table("catalog_merge_event")
    op.drop_table("catalog_duplicate_candidate")
    op.drop_table("catalog_upc_conflict")
    op.drop_table("catalog_import_error")
    op.drop_table("catalog_import_job")
