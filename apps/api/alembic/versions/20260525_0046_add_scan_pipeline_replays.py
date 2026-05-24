"""P34-08 scan pipeline replay / recovery bookkeeping (compare-only).

Revision ID: 20260525_0046
Revises: 20260525_0045
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0046"
down_revision: str | None = "20260525_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scan_pipeline_replay_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_session_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("replay_version", sa.String(length=80), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=28), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancelled_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["scan_session_id"], ["scan_session.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_pipeline_replay_run_scan_session_id", "scan_pipeline_replay_run", ["scan_session_id"])
    op.create_index("ix_scan_pipeline_replay_run_owner_user_id", "scan_pipeline_replay_run", ["owner_user_id"])
    op.create_index("ix_scan_pipeline_replay_run_replay_version", "scan_pipeline_replay_run", ["replay_version"])
    op.create_index("ix_scan_pipeline_replay_run_cancellation_requested", "scan_pipeline_replay_run", ["cancellation_requested"])
    op.create_index("ix_scan_pipeline_replay_run_status", "scan_pipeline_replay_run", ["status"])

    op.create_table(
        "scan_pipeline_replay_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("scan_session_item_id", sa.Integer(), nullable=False),
        sa.Column("result_state", sa.String(length=20), nullable=False),
        sa.Column("baseline_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("replay_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("diff_categories_json", sa.JSON(), nullable=False),
        sa.Column("diff_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["replay_run_id"], ["scan_pipeline_replay_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_session_item_id"], ["scan_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "scan_session_item_id", name="uq_scan_pipeline_replay_item_run_item"),
    )
    op.create_index("ix_scan_pipeline_replay_item_replay_run_id", "scan_pipeline_replay_item", ["replay_run_id"])
    op.create_index("ix_scan_pipeline_replay_item_scan_session_item_id", "scan_pipeline_replay_item", ["scan_session_item_id"])
    op.create_index("ix_scan_pipeline_replay_item_result_state", "scan_pipeline_replay_item", ["result_state"])


def downgrade() -> None:
    op.drop_table("scan_pipeline_replay_item")
    op.drop_table("scan_pipeline_replay_run")
