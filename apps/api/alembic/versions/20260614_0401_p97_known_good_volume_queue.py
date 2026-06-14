"""p97 known good volume queue + request ledger

Revision ID: 20260614_0401
Revises: 20260614_0301
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0401"
down_revision = "20260614_0301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p97_comicvine_volume_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comicvine_volume_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("series_name", sa.String(length=512), nullable=True),
        sa.Column("source_query", sa.String(length=512), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="existing_catalog"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("estimated_issue_count", sa.Integer(), nullable=True),
        sa.Column("issues_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issues_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("images_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comicvine_volume_id", name="uq_p97_volume_queue_comicvine_volume_id"),
    )
    op.create_index(
        "ix_p97_comicvine_volume_queue_comicvine_volume_id",
        "p97_comicvine_volume_queue",
        ["comicvine_volume_id"],
        unique=True,
    )
    op.create_index("ix_p97_comicvine_volume_queue_status", "p97_comicvine_volume_queue", ["status"])
    op.create_index("ix_p97_comicvine_volume_queue_priority", "p97_comicvine_volume_queue", ["priority"])
    op.create_index("ix_p97_comicvine_volume_queue_publisher", "p97_comicvine_volume_queue", ["publisher"])
    op.create_index("ix_p97_comicvine_volume_queue_series_name", "p97_comicvine_volume_queue", ["series_name"])

    op.create_table(
        "p97_comicvine_request_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        sa.Column("comicvine_volume_id", sa.Integer(), nullable=True),
        sa.Column("queue_id", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("was_420", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p97_comicvine_request_ledger_created_at", "p97_comicvine_request_ledger", ["created_at"])
    op.create_index("ix_p97_comicvine_request_ledger_was_420", "p97_comicvine_request_ledger", ["was_420"])
    op.create_index(
        "ix_p97_comicvine_request_ledger_comicvine_volume_id",
        "p97_comicvine_request_ledger",
        ["comicvine_volume_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p97_comicvine_request_ledger_comicvine_volume_id", table_name="p97_comicvine_request_ledger")
    op.drop_index("ix_p97_comicvine_request_ledger_was_420", table_name="p97_comicvine_request_ledger")
    op.drop_index("ix_p97_comicvine_request_ledger_created_at", table_name="p97_comicvine_request_ledger")
    op.drop_table("p97_comicvine_request_ledger")

    op.drop_index("ix_p97_comicvine_volume_queue_series_name", table_name="p97_comicvine_volume_queue")
    op.drop_index("ix_p97_comicvine_volume_queue_publisher", table_name="p97_comicvine_volume_queue")
    op.drop_index("ix_p97_comicvine_volume_queue_priority", table_name="p97_comicvine_volume_queue")
    op.drop_index("ix_p97_comicvine_volume_queue_status", table_name="p97_comicvine_volume_queue")
    op.drop_index("ix_p97_comicvine_volume_queue_comicvine_volume_id", table_name="p97_comicvine_volume_queue")
    op.drop_table("p97_comicvine_volume_queue")
