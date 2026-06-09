"""add receiving workflow foundation

Revision ID: 20261012_0220
Revises: 20261012_0219
Create Date: 2026-10-12 02:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0220"
down_revision = "20261012_0219"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receiving_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("verified_items", sa.Integer(), nullable=False),
        sa.Column("review_items", sa.Integer(), nullable=False),
        sa.Column("unknown_items", sa.Integer(), nullable=False),
        sa.Column("confirmed_items", sa.Integer(), nullable=False),
        sa.Column("skipped_items", sa.Integer(), nullable=False),
        sa.Column("session_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receiving_session_owner_user_id", "receiving_session", ["owner_user_id"])
    op.create_index("ix_receiving_session_status", "receiving_session", ["status"])

    op.create_table(
        "receiving_session_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receiving_session_id", sa.Integer(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=510), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=True),
        sa.Column("recognition_bucket", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recognition_confidence", sa.Float(), nullable=True),
        sa.Column("recognition_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("candidate_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("selected_candidate_index", sa.Integer(), nullable=True),
        sa.Column("selected_candidate_json", sa.JSON(), nullable=True),
        sa.Column("action_taken", sa.String(length=40), nullable=True),
        sa.Column("action_reason", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["receiving_session_id"], ["receiving_session.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receiving_session_id", "sequence_index", name="uq_receiving_session_item_sequence_idx"),
    )
    op.create_index(
        "ix_receiving_session_item_receiving_session_id",
        "receiving_session_item",
        ["receiving_session_id"],
    )
    op.create_index("ix_receiving_session_item_status", "receiving_session_item", ["status"])
    op.create_index("ix_receiving_session_item_recognition_bucket", "receiving_session_item", ["recognition_bucket"])
    op.create_index("ix_receiving_session_item_image_sha256", "receiving_session_item", ["image_sha256"])


def downgrade() -> None:
    op.drop_index("ix_receiving_session_item_image_sha256", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_recognition_bucket", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_status", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_receiving_session_id", table_name="receiving_session_item")
    op.drop_table("receiving_session_item")

    op.drop_index("ix_receiving_session_status", table_name="receiving_session")
    op.drop_index("ix_receiving_session_owner_user_id", table_name="receiving_session")
    op.drop_table("receiving_session")

