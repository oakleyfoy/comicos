"""add catalog cover assets and hydration runs (P104)

Revision ID: 20261012_0223
Revises: 20261012_0224
Create Date: 2026-10-12 02:23:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0223"
down_revision = "20261012_0224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_cover_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("catalog_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("priority_tier", sa.String(length=32), nullable=False, server_default="catalog"),
        sa.Column("original_path", sa.Text(), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("small_path", sa.Text(), nullable=True),
        sa.Column("medium_path", sa.Text(), nullable=True),
        sa.Column("large_path", sa.Text(), nullable=True),
        sa.Column("original_sha256", sa.String(length=64), nullable=True),
        sa.Column("perceptual_hash", sa.String(length=64), nullable=True),
        sa.Column("average_hash", sa.String(length=64), nullable=True),
        sa.Column("difference_hash", sa.String(length=64), nullable=True),
        sa.Column("color_histogram", sa.String(length=64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("download_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["catalog_issue_id"], ["catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_issue_id", "source_url", name="uq_catalog_cover_assets_issue_url"),
    )
    op.create_index(
        "ix_catalog_cover_assets_status_priority",
        "catalog_cover_assets",
        ["status", "priority_score", "id"],
    )
    op.create_index("ix_catalog_cover_assets_issue", "catalog_cover_assets", ["catalog_issue_id"])
    op.create_index("ix_catalog_cover_assets_original_sha256", "catalog_cover_assets", ["original_sha256"])

    op.create_table(
        "catalog_cover_hydration_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("requested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_no_url", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log_path", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_cover_hydration_runs_status", "catalog_cover_hydration_runs", ["status"])


def downgrade() -> None:
    op.drop_table("catalog_cover_hydration_runs")
    op.drop_table("catalog_cover_assets")
