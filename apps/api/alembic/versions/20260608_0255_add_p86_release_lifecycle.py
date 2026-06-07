"""add p86 release lifecycle automation

Revision ID: 20260608_0255
Revises: 20260607_0254
Create Date: 2026-06-08 03:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0255"
down_revision = "20260607_0254"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p86_release_lifecycle_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("anchor_release_date", sa.Date(), nullable=False),
        sa.Column("target_release_date", sa.Date(), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=32), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_seconds", sa.Float(), nullable=True),
        sa.Column("parent_queue_count", sa.Integer(), nullable=True),
        sa.Column("parent_captured_count", sa.Integer(), nullable=True),
        sa.Column("issue_count", sa.Integer(), nullable=True),
        sa.Column("variant_count", sa.Integer(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("failures_json", sa.JSON(), nullable=False),
        sa.Column("raw_path", sa.String(length=512), nullable=False),
        sa.Column("crosswalk_skipped", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p86_rl_run_owner_run_date", "p86_release_lifecycle_run", ["owner_id", "run_date", "id"])
    op.create_index("ix_p86_rl_run_owner_status", "p86_release_lifecycle_run", ["owner_id", "status", "id"])
    op.create_index(
        "ix_p86_rl_run_owner_anchor_stage",
        "p86_release_lifecycle_run",
        ["owner_id", "anchor_release_date", "lifecycle_stage", "run_date"],
    )
    op.create_index(op.f("ix_p86_release_lifecycle_run_owner_id"), "p86_release_lifecycle_run", ["owner_id"])
    op.create_index(
        op.f("ix_p86_release_lifecycle_run_run_date"), "p86_release_lifecycle_run", ["run_date"]
    )
    op.create_index(
        op.f("ix_p86_release_lifecycle_run_anchor_release_date"),
        "p86_release_lifecycle_run",
        ["anchor_release_date"],
    )
    op.create_index(
        op.f("ix_p86_release_lifecycle_run_target_release_date"),
        "p86_release_lifecycle_run",
        ["target_release_date"],
    )
    op.create_index(
        op.f("ix_p86_release_lifecycle_run_lifecycle_stage"),
        "p86_release_lifecycle_run",
        ["lifecycle_stage"],
    )
    op.create_index(op.f("ix_p86_release_lifecycle_run_status"), "p86_release_lifecycle_run", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p86_release_lifecycle_run_status"), table_name="p86_release_lifecycle_run")
    op.drop_index(op.f("ix_p86_release_lifecycle_run_lifecycle_stage"), table_name="p86_release_lifecycle_run")
    op.drop_index(
        op.f("ix_p86_release_lifecycle_run_target_release_date"), table_name="p86_release_lifecycle_run"
    )
    op.drop_index(
        op.f("ix_p86_release_lifecycle_run_anchor_release_date"), table_name="p86_release_lifecycle_run"
    )
    op.drop_index(op.f("ix_p86_release_lifecycle_run_run_date"), table_name="p86_release_lifecycle_run")
    op.drop_index(op.f("ix_p86_release_lifecycle_run_owner_id"), table_name="p86_release_lifecycle_run")
    op.drop_index("ix_p86_rl_run_owner_anchor_stage", table_name="p86_release_lifecycle_run")
    op.drop_index("ix_p86_rl_run_owner_status", table_name="p86_release_lifecycle_run")
    op.drop_index("ix_p86_rl_run_owner_run_date", table_name="p86_release_lifecycle_run")
    op.drop_table("p86_release_lifecycle_run")
