"""P97 volume issue import queue (from comicvine_volume_universe)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_0201"
down_revision = "20260615_0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p97_volume_issue_import_queue",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("comicvine_volume_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("count_of_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("existing_issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("comicvine_volume_id", name="uq_p97_volume_issue_import_queue_cv_volume"),
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_comicvine_volume_id",
        "p97_volume_issue_import_queue",
        ["comicvine_volume_id"],
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_status",
        "p97_volume_issue_import_queue",
        ["status"],
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_priority_score",
        "p97_volume_issue_import_queue",
        ["priority_score"],
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_missing_issue_count",
        "p97_volume_issue_import_queue",
        ["missing_issue_count"],
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_publisher",
        "p97_volume_issue_import_queue",
        ["publisher"],
    )


def downgrade() -> None:
    op.drop_index("ix_p97_volume_issue_import_queue_publisher", table_name="p97_volume_issue_import_queue")
    op.drop_index(
        "ix_p97_volume_issue_import_queue_missing_issue_count",
        table_name="p97_volume_issue_import_queue",
    )
    op.drop_index(
        "ix_p97_volume_issue_import_queue_priority_score",
        table_name="p97_volume_issue_import_queue",
    )
    op.drop_index("ix_p97_volume_issue_import_queue_status", table_name="p97_volume_issue_import_queue")
    op.drop_index(
        "ix_p97_volume_issue_import_queue_comicvine_volume_id",
        table_name="p97_volume_issue_import_queue",
    )
    op.drop_table("p97_volume_issue_import_queue")
