"""add scan ingestion layer

Revision ID: 20260528_0085
Revises: 20260528_0084
Create Date: 2026-05-28 11:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260528_0085"
down_revision = "20260528_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_upload_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("upload_source", sa.String(length=40), nullable=False),
        sa.Column("session_checksum", sa.String(length=64), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("successful_files", sa.Integer(), nullable=False),
        sa.Column("failed_files", sa.Integer(), nullable=False),
        sa.Column("duplicate_files", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "session_checksum", name="uq_scan_upload_session_owner_checksum"),
    )
    op.create_index("ix_scan_upload_session_owner_user_id", "scan_upload_session", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_upload_session_upload_source", "scan_upload_session", ["upload_source"], unique=False)
    op.create_index("ix_scan_upload_session_session_checksum", "scan_upload_session", ["session_checksum"], unique=False)
    op.create_index("ix_scan_upload_session_owner_created", "scan_upload_session", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_upload_session_source", "scan_upload_session", ["upload_source", "id"], unique=False)

    op.create_table(
        "scan_ingestion_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("upload_session_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("batch_status", sa.String(length=24), nullable=False),
        sa.Column("image_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("ingestion_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["upload_session_id"], ["scan_upload_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "ingestion_checksum", name="uq_scan_ingestion_batch_owner_checksum"),
    )
    op.create_index("ix_scan_ingestion_batch_owner_user_id", "scan_ingestion_batch", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_ingestion_batch_upload_session_id", "scan_ingestion_batch", ["upload_session_id"], unique=False)
    op.create_index("ix_scan_ingestion_batch_source_type", "scan_ingestion_batch", ["source_type"], unique=False)
    op.create_index("ix_scan_ingestion_batch_batch_status", "scan_ingestion_batch", ["batch_status"], unique=False)
    op.create_index("ix_scan_ingestion_batch_ingestion_checksum", "scan_ingestion_batch", ["ingestion_checksum"], unique=False)
    op.create_index("ix_scan_ingestion_batch_owner_created", "scan_ingestion_batch", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ingestion_batch_owner_status", "scan_ingestion_batch", ["owner_user_id", "batch_status", "id"], unique=False)
    op.create_index("ix_scan_ingestion_batch_source", "scan_ingestion_batch", ["source_type", "id"], unique=False)

    op.create_table(
        "scan_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("dpi_x", sa.Integer(), nullable=True),
        sa.Column("dpi_y", sa.Integer(), nullable=True),
        sa.Column("normalized_dpi_x", sa.Integer(), nullable=True),
        sa.Column("normalized_dpi_y", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_checksum", sa.String(length=64), nullable=False),
        sa.Column("scanner_make", sa.String(length=120), nullable=True),
        sa.Column("scanner_model", sa.String(length=120), nullable=True),
        sa.Column("scanner_profile", sa.String(length=200), nullable=True),
        sa.Column("color_mode", sa.String(length=40), nullable=True),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("duplicate_of_scan_image_id", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_of_scan_image_id"], ["scan_image.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["scan_ingestion_batch.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingestion_batch_id", "sequence_index", name="uq_scan_image_batch_sequence"),
    )
    op.create_index("ix_scan_image_owner_user_id", "scan_image", ["owner_user_id"], unique=False)
    op.create_index("ix_scan_image_ingestion_batch_id", "scan_image", ["ingestion_batch_id"], unique=False)
    op.create_index("ix_scan_image_sequence_index", "scan_image", ["sequence_index"], unique=False)
    op.create_index("ix_scan_image_storage_backend", "scan_image", ["storage_backend"], unique=False)
    op.create_index("ix_scan_image_sha256_checksum", "scan_image", ["sha256_checksum"], unique=False)
    op.create_index("ix_scan_image_processing_status", "scan_image", ["processing_status"], unique=False)
    op.create_index("ix_scan_image_is_duplicate", "scan_image", ["is_duplicate"], unique=False)
    op.create_index("ix_scan_image_duplicate_of_scan_image_id", "scan_image", ["duplicate_of_scan_image_id"], unique=False)
    op.create_index("ix_scan_image_owner_created", "scan_image", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_image_owner_status", "scan_image", ["owner_user_id", "processing_status", "id"], unique=False)
    op.create_index("ix_scan_image_owner_checksum", "scan_image", ["owner_user_id", "sha256_checksum", "id"], unique=False)
    op.create_index("ix_scan_image_dup_ref", "scan_image", ["duplicate_of_scan_image_id", "id"], unique=False)

    op.create_table(
        "scan_image_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_scan_image_id", sa.Integer(), nullable=False),
        sa.Column("variant_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_scan_image_id", "variant_type", "checksum", name="uq_scan_variant_parent_type_checksum"),
    )
    op.create_index("ix_scan_image_variant_parent_scan_image_id", "scan_image_variant", ["parent_scan_image_id"], unique=False)
    op.create_index("ix_scan_image_variant_variant_type", "scan_image_variant", ["variant_type"], unique=False)
    op.create_index("ix_scan_image_variant_storage_backend", "scan_image_variant", ["storage_backend"], unique=False)
    op.create_index("ix_scan_image_variant_checksum", "scan_image_variant", ["checksum"], unique=False)
    op.create_index("ix_scan_variant_parent", "scan_image_variant", ["parent_scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_variant_type", "scan_image_variant", ["variant_type", "id"], unique=False)

    op.create_table(
        "scan_ingestion_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("scan_image_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["scan_ingestion_batch.id"]),
        sa.ForeignKeyConstraint(["scan_image_id"], ["scan_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_ingestion_event_ingestion_batch_id", "scan_ingestion_event", ["ingestion_batch_id"], unique=False)
    op.create_index("ix_scan_ingestion_event_scan_image_id", "scan_ingestion_event", ["scan_image_id"], unique=False)
    op.create_index("ix_scan_ingestion_event_event_type", "scan_ingestion_event", ["event_type"], unique=False)
    op.create_index("ix_scan_ingestion_event_batch", "scan_ingestion_event", ["ingestion_batch_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ingestion_event_image", "scan_ingestion_event", ["scan_image_id", "created_at", "id"], unique=False)
    op.create_index("ix_scan_ingestion_event_type", "scan_ingestion_event", ["event_type", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scan_ingestion_event_type", table_name="scan_ingestion_event")
    op.drop_index("ix_scan_ingestion_event_image", table_name="scan_ingestion_event")
    op.drop_index("ix_scan_ingestion_event_batch", table_name="scan_ingestion_event")
    op.drop_index("ix_scan_ingestion_event_event_type", table_name="scan_ingestion_event")
    op.drop_index("ix_scan_ingestion_event_scan_image_id", table_name="scan_ingestion_event")
    op.drop_index("ix_scan_ingestion_event_ingestion_batch_id", table_name="scan_ingestion_event")
    op.drop_table("scan_ingestion_event")

    op.drop_index("ix_scan_variant_type", table_name="scan_image_variant")
    op.drop_index("ix_scan_variant_parent", table_name="scan_image_variant")
    op.drop_index("ix_scan_image_variant_checksum", table_name="scan_image_variant")
    op.drop_index("ix_scan_image_variant_storage_backend", table_name="scan_image_variant")
    op.drop_index("ix_scan_image_variant_variant_type", table_name="scan_image_variant")
    op.drop_index("ix_scan_image_variant_parent_scan_image_id", table_name="scan_image_variant")
    op.drop_table("scan_image_variant")

    op.drop_index("ix_scan_image_dup_ref", table_name="scan_image")
    op.drop_index("ix_scan_image_owner_checksum", table_name="scan_image")
    op.drop_index("ix_scan_image_owner_status", table_name="scan_image")
    op.drop_index("ix_scan_image_owner_created", table_name="scan_image")
    op.drop_index("ix_scan_image_duplicate_of_scan_image_id", table_name="scan_image")
    op.drop_index("ix_scan_image_is_duplicate", table_name="scan_image")
    op.drop_index("ix_scan_image_processing_status", table_name="scan_image")
    op.drop_index("ix_scan_image_sha256_checksum", table_name="scan_image")
    op.drop_index("ix_scan_image_storage_backend", table_name="scan_image")
    op.drop_index("ix_scan_image_sequence_index", table_name="scan_image")
    op.drop_index("ix_scan_image_ingestion_batch_id", table_name="scan_image")
    op.drop_index("ix_scan_image_owner_user_id", table_name="scan_image")
    op.drop_table("scan_image")

    op.drop_index("ix_scan_ingestion_batch_source", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_owner_status", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_owner_created", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_ingestion_checksum", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_batch_status", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_source_type", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_upload_session_id", table_name="scan_ingestion_batch")
    op.drop_index("ix_scan_ingestion_batch_owner_user_id", table_name="scan_ingestion_batch")
    op.drop_table("scan_ingestion_batch")

    op.drop_index("ix_scan_upload_session_source", table_name="scan_upload_session")
    op.drop_index("ix_scan_upload_session_owner_created", table_name="scan_upload_session")
    op.drop_index("ix_scan_upload_session_session_checksum", table_name="scan_upload_session")
    op.drop_index("ix_scan_upload_session_upload_source", table_name="scan_upload_session")
    op.drop_index("ix_scan_upload_session_owner_user_id", table_name="scan_upload_session")
    op.drop_table("scan_upload_session")
