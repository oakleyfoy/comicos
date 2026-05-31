"""add pull list decision foundation (P52-02)

Revision ID: 20260823_0173
Revises: 20260822_0172
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260823_0173"
down_revision = "20260822_0172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_list_decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_list_decision_owner_user_id", "pull_list_decision", ["owner_user_id"])
    op.create_index("ix_pull_list_decision_release_id", "pull_list_decision", ["release_id"])
    op.create_index("ix_pull_list_decision_decision_type", "pull_list_decision", ["decision_type"])
    op.create_index("ix_pull_list_decision_created_at", "pull_list_decision", ["created_at"])
    op.create_index("ix_pull_list_decision_owner_created", "pull_list_decision", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_pull_list_decision_owner_release", "pull_list_decision", ["owner_user_id", "release_id", "id"])
    op.create_index("ix_pull_list_decision_owner_type", "pull_list_decision", ["owner_user_id", "decision_type", "id"])


def downgrade() -> None:
    op.drop_table("pull_list_decision")
