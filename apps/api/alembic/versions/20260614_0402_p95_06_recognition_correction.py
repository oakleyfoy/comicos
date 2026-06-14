"""p95-06 recognition review & correction workflow

Revision ID: 20260614_0402
Revises: 20260614_0401
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0402"
down_revision = "20260614_0401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receiving_session_item",
        sa.Column("original_recognition_snapshot_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("corrected_recognition_snapshot_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("corrected_catalog_issue_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("user_corrected", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("correction_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("user_corrected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "receiving_session_item",
        sa.Column("user_corrected_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_receiving_session_item_corrected_catalog_issue_id",
        "receiving_session_item",
        ["corrected_catalog_issue_id"],
    )
    op.create_index(
        "ix_receiving_session_item_user_corrected_by",
        "receiving_session_item",
        ["user_corrected_by"],
    )

    op.create_table(
        "recognition_correction_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("receiving_session_id", sa.Integer(), nullable=False),
        sa.Column("receiving_session_item_id", sa.Integer(), nullable=False),
        sa.Column("original_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("corrected_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("original_confidence", sa.Float(), nullable=True),
        sa.Column("original_source", sa.String(length=64), nullable=True),
        sa.Column("correction_reason", sa.String(length=64), nullable=True),
        sa.Column("captured_image_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["receiving_session_id"], ["receiving_session.id"]),
        sa.ForeignKeyConstraint(["receiving_session_item_id"], ["receiving_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recognition_correction_event_user_id", "recognition_correction_event", ["user_id"])
    op.create_index(
        "ix_recognition_correction_event_receiving_session_id",
        "recognition_correction_event",
        ["receiving_session_id"],
    )
    op.create_index(
        "ix_recognition_correction_event_receiving_session_item_id",
        "recognition_correction_event",
        ["receiving_session_item_id"],
    )
    op.create_index(
        "ix_recognition_correction_event_original_catalog_issue_id",
        "recognition_correction_event",
        ["original_catalog_issue_id"],
    )
    op.create_index(
        "ix_recognition_correction_event_corrected_catalog_issue_id",
        "recognition_correction_event",
        ["corrected_catalog_issue_id"],
    )
    op.create_index(
        "ix_recognition_correction_event_captured_image_sha256",
        "recognition_correction_event",
        ["captured_image_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_recognition_correction_event_captured_image_sha256", table_name="recognition_correction_event")
    op.drop_index("ix_recognition_correction_event_corrected_catalog_issue_id", table_name="recognition_correction_event")
    op.drop_index("ix_recognition_correction_event_original_catalog_issue_id", table_name="recognition_correction_event")
    op.drop_index("ix_recognition_correction_event_receiving_session_item_id", table_name="recognition_correction_event")
    op.drop_index("ix_recognition_correction_event_receiving_session_id", table_name="recognition_correction_event")
    op.drop_index("ix_recognition_correction_event_user_id", table_name="recognition_correction_event")
    op.drop_table("recognition_correction_event")

    op.drop_index("ix_receiving_session_item_user_corrected_by", table_name="receiving_session_item")
    op.drop_index("ix_receiving_session_item_corrected_catalog_issue_id", table_name="receiving_session_item")
    op.drop_column("receiving_session_item", "user_corrected_by")
    op.drop_column("receiving_session_item", "user_corrected_at")
    op.drop_column("receiving_session_item", "correction_reason")
    op.drop_column("receiving_session_item", "user_corrected")
    op.drop_column("receiving_session_item", "corrected_catalog_issue_id")
    op.drop_column("receiving_session_item", "corrected_recognition_snapshot_json")
    op.drop_column("receiving_session_item", "original_recognition_snapshot_json")
