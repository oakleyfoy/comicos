"""add external catalog tables

Revision ID: 20261008_0214
Revises: 20261007_0213
Create Date: 2026-10-08 02:14:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261008_0214"
down_revision = "20261007_0213"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_catalog_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_catalog_source_source_name", "external_catalog_source", ["source_name"])
    op.create_index("ix_external_catalog_source_name_active", "external_catalog_source", ["source_name", "is_active"])

    op.create_table(
        "external_catalog_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_issue_id", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=True),
        sa.Column("issue_title", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("cover_date", sa.Date(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pull_count", sa.Integer(), nullable=True),
        sa.Column("want_count", sa.Integer(), nullable=True),
        sa.Column("variant_count", sa.Integer(), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("normalized_title_key", sa.String(length=320), nullable=False),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "source_url", name="uq_external_catalog_issue_source_url"),
    )
    op.create_index("ix_external_catalog_issue_source_name", "external_catalog_issue", ["source_name"])
    op.create_index("ix_external_catalog_issue_source_release", "external_catalog_issue", ["source_name", "release_date"])
    op.create_index("ix_external_catalog_issue_source_foc", "external_catalog_issue", ["source_name", "foc_date"])
    op.create_index("ix_external_catalog_issue_normalized_title_key", "external_catalog_issue", ["normalized_title_key"])
    op.create_index("ix_external_catalog_issue_sync_status", "external_catalog_issue", ["sync_status"])

    op.create_table(
        "external_catalog_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("cover_label", sa.String(length=64), nullable=True),
        sa.Column("variant_name", sa.String(length=200), nullable=True),
        sa.Column("artist", sa.String(length=160), nullable=True),
        sa.Column("ratio_value", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_issue_id",
            "cover_label",
            "variant_name",
            name="uq_external_catalog_variant_identity",
        ),
    )
    op.create_index("ix_external_catalog_variant_issue", "external_catalog_variant", ["external_issue_id", "id"])

    op.create_table(
        "external_catalog_creator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("creator_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_issue_id",
            "creator_name",
            "role",
            name="uq_external_catalog_creator_identity",
        ),
    )
    op.create_index("ix_external_catalog_creator_issue", "external_catalog_creator", ["external_issue_id", "id"])

    op.create_table(
        "external_catalog_sync_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("sync_type", sa.String(length=24), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("pages_scanned", sa.Integer(), nullable=False),
        sa.Column("issues_created", sa.Integer(), nullable=False),
        sa.Column("issues_updated", sa.Integer(), nullable=False),
        sa.Column("variants_created", sa.Integer(), nullable=False),
        sa.Column("creators_created", sa.Integer(), nullable=False),
        sa.Column("errors_count", sa.Integer(), nullable=False),
        sa.Column("error_sample", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_catalog_sync_run_source_status", "external_catalog_sync_run", ["source_name", "status", "started_at"])

    op.create_table(
        "external_catalog_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("match_status", sa.String(length=32), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_issue_id", "owner_user_id", name="uq_external_catalog_match_issue_owner"),
    )
    op.create_index("ix_external_catalog_match_match_status", "external_catalog_match", ["match_status"])
    op.create_index("ix_external_catalog_match_release_issue_id", "external_catalog_match", ["release_issue_id"])


def downgrade() -> None:
    op.drop_table("external_catalog_match")
    op.drop_table("external_catalog_sync_run")
    op.drop_table("external_catalog_creator")
    op.drop_table("external_catalog_variant")
    op.drop_table("external_catalog_issue")
    op.drop_table("external_catalog_source")
