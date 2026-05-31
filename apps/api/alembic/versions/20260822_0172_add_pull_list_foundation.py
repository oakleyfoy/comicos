"""add pull list foundation (P52-01)

Revision ID: 20260822_0172
Revises: 20260821_0171
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260822_0172"
down_revision = "20260821_0171"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_list",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("canonical_series_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_list_owner_user_id", "pull_list", ["owner_user_id"])
    op.create_index("ix_pull_list_status", "pull_list", ["status"])
    op.create_index("ix_pull_list_publisher", "pull_list", ["publisher"])
    op.create_index("ix_pull_list_series_name", "pull_list", ["series_name"])
    op.create_index("ix_pull_list_canonical_series_id", "pull_list", ["canonical_series_id"])
    op.create_index("ix_pull_list_owner_status", "pull_list", ["owner_user_id", "status", "id"])
    op.create_index("ix_pull_list_owner_publisher", "pull_list", ["owner_user_id", "publisher", "id"])
    op.create_index("ix_pull_list_owner_series", "pull_list", ["owner_user_id", "series_name", "id"])

    op.create_table(
        "pull_list_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pull_list_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("action_state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pull_list_id"], ["pull_list.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pull_list_id", "release_id", name="uq_pull_list_issue_release"),
    )
    op.create_index("ix_pull_list_issue_pull_list_id", "pull_list_issue", ["pull_list_id"])
    op.create_index("ix_pull_list_issue_release_id", "pull_list_issue", ["release_id"])
    op.create_index("ix_pull_list_issue_release_date", "pull_list_issue", ["release_date"])
    op.create_index("ix_pull_list_issue_foc_date", "pull_list_issue", ["foc_date"])
    op.create_index("ix_pull_list_issue_action_state", "pull_list_issue", ["action_state"])
    op.create_index("ix_pull_list_issue_list_release_date", "pull_list_issue", ["pull_list_id", "release_date", "id"])
    op.create_index("ix_pull_list_issue_list_foc_date", "pull_list_issue", ["pull_list_id", "foc_date", "id"])
    op.create_index("ix_pull_list_issue_list_action", "pull_list_issue", ["pull_list_id", "action_state", "id"])


def downgrade() -> None:
    op.drop_table("pull_list_issue")
    op.drop_table("pull_list")
