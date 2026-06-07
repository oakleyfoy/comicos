"""add p86 release lifecycle report

Revision ID: 20260608_0256
Revises: 20260608_0255
Create Date: 2026-06-08 04:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0256"
down_revision = "20260608_0255"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p86_release_lifecycle_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("anchor_release_date", sa.Date(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("overall_status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("runs_json", sa.JSON(), nullable=False),
        sa.Column("action_url", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p86_rl_report_owner_created", "p86_release_lifecycle_report", ["owner_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_p86_rl_report_owner_created", table_name="p86_release_lifecycle_report")
    op.drop_table("p86_release_lifecycle_report")
