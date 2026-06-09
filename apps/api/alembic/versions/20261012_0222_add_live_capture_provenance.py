"""add live capture provenance

Revision ID: 20261012_0222
Revises: 20261012_0221
Create Date: 2026-10-12 02:22:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0222"
down_revision = "20261012_0221"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("receiving_session", sa.Column("capture_source", sa.String(length=40), nullable=True))
    op.add_column(
        "receiving_session",
        sa.Column("live_capture_stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_receiving_session_capture_source", "receiving_session", ["capture_source"])

    op.add_column("receiving_session_item", sa.Column("capture_source", sa.String(length=40), nullable=True))
    op.add_column("receiving_session_item", sa.Column("frame_fingerprint", sa.String(length=64), nullable=True))
    op.add_column("receiving_session_item", sa.Column("frame_sequence_index", sa.Integer(), nullable=True))
    op.add_column("receiving_session_item", sa.Column("stable_frame_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("receiving_session_item", sa.Column("recognition_latency_ms", sa.Integer(), nullable=True))
    op.add_column(
        "receiving_session_item",
        sa.Column("capture_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("capture_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("duplicate_of_item_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("duplicate_suppressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("capture_metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_receiving_session_item_capture_source", "receiving_session_item", ["capture_source"])
    op.create_index("ix_receiving_session_item_frame_fingerprint", "receiving_session_item", ["frame_fingerprint"])
    op.create_index("ix_receiving_session_item_frame_sequence_index", "receiving_session_item", ["frame_sequence_index"])
    op.create_index("ix_receiving_session_item_duplicate_of_item_id", "receiving_session_item", ["duplicate_of_item_id"])
    op.create_foreign_key(
        "fk_receiving_item_dup_of_item_id",
        "receiving_session_item",
        "receiving_session_item",
        ["duplicate_of_item_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_receiving_item_dup_of_item_id",
        "receiving_session_item",
        type_="foreignkey",
    )
    op.drop_index("ix_receiving_session_item_duplicate_of_item_id", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_frame_sequence_index", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_frame_fingerprint", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_capture_source", table_name="receiving_session_item")
    op.drop_column("receiving_session_item", "capture_metadata_json")
    op.drop_column("receiving_session_item", "duplicate_suppressed")
    op.drop_column("receiving_session_item", "duplicate_of_item_id")
    op.drop_column("receiving_session_item", "capture_completed_at")
    op.drop_column("receiving_session_item", "capture_started_at")
    op.drop_column("receiving_session_item", "recognition_latency_ms")
    op.drop_column("receiving_session_item", "stable_frame_count")
    op.drop_column("receiving_session_item", "frame_sequence_index")
    op.drop_column("receiving_session_item", "frame_fingerprint")
    op.drop_column("receiving_session_item", "capture_source")

    op.drop_index("ix_receiving_session_capture_source", table_name="receiving_session")
    op.drop_column("receiving_session", "live_capture_stats_json")
    op.drop_column("receiving_session", "capture_source")
