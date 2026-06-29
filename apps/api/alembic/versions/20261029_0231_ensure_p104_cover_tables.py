"""Ensure P104 cover hydration tables exist (repair stamped-without-DDL databases).

Original table creation: 20261012_0223_add_p104_cover_hydration.py
last_hydration_run_id column: 20261027_0227_add_p104_last_hydration_run_id.py

Some local databases were stamped at alembic head without running 20261012_0223,
so ``alembic upgrade head`` applies no ops while ``catalog_cover_assets`` is missing.

Revision ID: 20261029_0231
Revises: 20261028_0230
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20261029_0231"
down_revision = "20261028_0230"
branch_labels = None
depends_on = None


def _create_catalog_cover_assets_if_missing(bind: sa.engine.Connection) -> None:
    insp = inspect(bind)
    if insp.has_table("catalog_cover_assets"):
        return
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
        sa.Column("last_hydration_run_id", sa.BigInteger(), nullable=True),
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
    op.create_index(
        "ix_catalog_cover_assets_last_hydration_run_id",
        "catalog_cover_assets",
        ["last_hydration_run_id"],
    )


def _create_catalog_cover_hydration_runs_if_missing(bind: sa.engine.Connection) -> None:
    insp = inspect(bind)
    if insp.has_table("catalog_cover_hydration_runs"):
        return
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


def _ensure_last_hydration_run_id_column(bind: sa.engine.Connection) -> None:
    insp = inspect(bind)
    if not insp.has_table("catalog_cover_assets"):
        return
    cols = {c["name"] for c in insp.get_columns("catalog_cover_assets")}
    if "last_hydration_run_id" in cols:
        return
    op.add_column(
        "catalog_cover_assets",
        sa.Column("last_hydration_run_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_catalog_cover_assets_last_hydration_run_id",
        "catalog_cover_assets",
        ["last_hydration_run_id"],
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_catalog_cover_assets_if_missing(bind)
    _create_catalog_cover_hydration_runs_if_missing(bind)
    _ensure_last_hydration_run_id_column(bind)


def downgrade() -> None:
    """No-op repair migration; do not drop production hydration data."""
